//! AgentsFramework macOS shell (Tauri 2).
//!
//! The web app is **server-dependent** (`next.config output: "standalone"` +
//! WorkOS AuthKit middleware + BFF API routes), so this shell does NOT bundle
//! static files — it loads a running HTTP origin:
//!   - debug  → the local dev server (`devUrl` in tauri.conf.json, localhost:3000)
//!   - release → the deployed Cloud Run BFF (PROD_URL below)
//!
//! Override either with the `AF_SHELL_URL` env var (e.g. point the dev shell at
//! the deployed URL for an auth spike, or at staging). When set, the window is
//! navigated there on setup regardless of build profile.
//!
//! Auth (P5 Step 2): a web sign-in navigation is intercepted and replaced with a
//! system-browser flow; WorkOS returns via the `agentsframework://` deep link,
//! which we rewrite to the HTTPS desktop-callback that seals the session cookie
//! in the webview. PKCE verifier stays in the shell (RFC 8252). See `auth.rs` +
//! docs/plans/p5_step2_auth_deeplink.design.md.

mod auth;

use std::sync::Mutex;
use tauri::{Manager, WebviewWindowBuilder};
use tauri_plugin_deep_link::DeepLinkExt;

/// Deployed Cloud Run BFF the release build points at.
const PROD_URL: &str = "https://agent-frontend-590652793393.us-central1.run.app";

/// The origin the shell loads (and thus the origin its BFF auth routes live on).
fn shell_origin() -> String {
    if let Ok(url) = std::env::var("AF_SHELL_URL") {
        if !url.trim().is_empty() {
            return url;
        }
    }
    if cfg!(debug_assertions) {
        "http://localhost:3000".to_string()
    } else {
        PROD_URL.to_string()
    }
}

/// Resolve the URL to navigate the window to on setup: override / release prod;
/// plain debug keeps the config `devUrl` (returns None).
fn target_url() -> Option<String> {
    if let Ok(url) = std::env::var("AF_SHELL_URL") {
        if !url.trim().is_empty() {
            return Some(url);
        }
    }
    if cfg!(debug_assertions) {
        None
    } else {
        Some(PROD_URL.to_string())
    }
}

/// In-flight PKCE session (one sign-in at a time). Held in the shell only;
/// the verifier is attached to a matching deep-link return, then cleared.
#[derive(Default)]
struct AuthState(Mutex<Option<auth::PkceSession>>);

/// Handle an incoming deep link: if it's our auth callback and the state
/// matches the in-flight session, navigate the main webview to the HTTPS
/// desktop-callback (which seals the session cookie), then clear the session.
fn handle_deep_link(app: &tauri::AppHandle, urls: &[url::Url]) {
    for url in urls {
        let raw = url.as_str();
        if !auth::is_auth_deep_link(raw) {
            continue;
        }
        let session = {
            let state = app.state::<AuthState>();
            let guard = state.0.lock().unwrap();
            guard.clone()
        };
        let Some(session) = session else {
            log::warn!("deep link auth callback with no in-flight session; ignoring");
            continue;
        };
        match auth::callback_url(&shell_origin(), raw, &session) {
            Some(callback) => {
                if let Some(window) = app.get_webview_window("main") {
                    if let Ok(parsed) = callback.parse() {
                        let _ = window.navigate(parsed);
                        let _ = window.set_focus();
                    }
                }
                // Single-use: clear the verifier after handing it off.
                let state = app.state::<AuthState>();
                *state.0.lock().unwrap() = None;
            }
            None => log::warn!("deep link auth callback failed validation (state mismatch?)"),
        }
    }
}

/// Build the main window from the config, attaching the navigation interceptor
/// that swaps the web sign-in for the system-browser flow.
fn build_main_window(app: &tauri::AppHandle) -> tauri::Result<()> {
    let config = app
        .config()
        .app
        .windows
        .first()
        .cloned()
        .expect("a [[app.windows]] entry in tauri.conf.json");

    let app_for_nav = app.clone();
    let builder = WebviewWindowBuilder::from_config(app, &config)?
        // P5 §4b: mark the document as running inside the native shell so the
        // shared web build can opt into macOS-only chrome (traffic-light
        // clearance) via `html.tauri-shell` CSS. Runs before page scripts in
        // every frame; the browser build never gets this class.
        .initialization_script(
            "document.documentElement.classList.add('tauri-shell');",
        )
        .on_navigation(move |url| {
        let raw = url.as_str();
        if auth::is_web_sign_in_nav(raw) {
            // Intercept: generate PKCE, stash it, open the system browser, and
            // cancel the in-webview navigation (return false).
            let session = auth::new_pkce_session();
            if let Ok(sign_in) = auth::sign_in_url(&shell_origin(), &session) {
                {
                    let state = app_for_nav.state::<AuthState>();
                    *state.0.lock().unwrap() = Some(session);
                }
                use tauri_plugin_opener::OpenerExt;
                if let Err(e) = app_for_nav.opener().open_url(sign_in, None::<&str>) {
                    log::error!("failed to open system browser for sign-in: {e}");
                }
            }
            return false;
        }
        true
    });

    builder.build()?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default();

    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // A second launch (e.g. the OS routing a deep link) focuses the
            // existing window; the deep-link plugin re-emits the URL event.
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }));
    }

    builder
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_deep_link::init())
        .manage(AuthState::default())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Build the main window ourselves so we can attach the navigation
            // interceptor (config defines it, but we need on_navigation).
            build_main_window(app.handle())?;

            // Navigate to the resolved origin (override / release prod). In plain
            // debug this is None and we keep the config `devUrl` (localhost).
            if let Some(target) = target_url() {
                if let Some(window) = app.get_webview_window("main") {
                    if let Ok(url) = target.parse() {
                        let _ = window.navigate(url);
                    }
                }
            }

            // Deep-link auth callback handler.
            let handle = app.handle().clone();
            app.deep_link().on_open_url(move |event| {
                handle_deep_link(&handle, &event.urls());
            });

            // On macOS/Linux dev, register the scheme at runtime so deep links
            // resolve without a bundled app. (No-op / already-registered on a
            // bundled build.)
            #[cfg(any(target_os = "linux", all(debug_assertions, target_os = "macos")))]
            {
                let _ = app.deep_link().register(auth::SCHEME);
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
