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
const PROD_URL: &str = "https://desktop---agent-frontend-w65nrxwkiq-uc.a.run.app";

/// Custom webview User-Agent. A realistic macOS Safari UA (so WorkOS hosted
/// login + Next treat the webview as a normal browser) with our marker token
/// appended. The BFF middleware matches the `AgentsFrameworkShell` token to relax
/// CSP `connect-src` for the Tauri IPC origin. Keep the token in sync with
/// `SHELL_UA_MARKER` in `middleware.ts`.
const SHELL_USER_AGENT: &str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15 AgentsFrameworkShell";

/// Shell-only init script (runs before page scripts): tags `html.tauri-shell`
/// for macOS chrome CSS. NOTE: under the deployed app's strict CSP this is
/// blocked, so it only takes effect on relaxed-CSP origins (dev). Auth does NOT
/// depend on it (see SIGN_IN_CLICK_SCRIPT, injected via eval which bypasses CSP).
const SHELL_INIT_SCRIPT: &str = r#"
(function () { document.documentElement.classList.add('tauri-shell'); })();
"#;

/// Sign-in click delegation, injected via `webview.eval()` on every page load.
/// `eval` runs at the WebKit host level and is NOT governed by the page CSP, so
/// it works even under the deployed strict nonce CSP that blocks init scripts.
/// Idempotent: a guard flag prevents double-binding across RSC navigations.
const SIGN_IN_CLICK_SCRIPT: &str = r#"
(function () {
  if (window.__afSignInBound) return;
  window.__afSignInBound = true;

  // Capture phase so we run before Next's client router handles the click.
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest
      ? e.target.closest('a[href*="/api/auth/sign-in"]')
      : null;
    if (!el) return;
    // Let the browser leg we open ourselves (?client=desktop) pass through.
    if ((el.getAttribute('href') || '').indexOf('client=desktop') !== -1) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    // Force a TOP-LEVEL document navigation to the sign-in URL. This surfaces in
    // the Rust `on_navigation` handler (`is_web_sign_in_nav`), which opens the
    // system browser via `begin_desktop_sign_in` and cancels the in-webview nav.
    // We deliberately AVOID the Tauri IPC (`invoke`) path here: the shell loads a
    // REMOTE https origin, where the `ipc://localhost` fetch transport is blocked
    // by WKWebView as insecure mixed content. The hard navigation needs no IPC,
    // no ACL, and no relaxed CSP — it reuses the proven nav-intercept path.
    var href = el.href || el.getAttribute('href');
    try { window.location.assign(href); }
    catch (err) { console.error('desktop sign-in nav failed:', err); }
  }, true);
})();
"#;

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

/// Start the desktop sign-in: generate a fresh PKCE session, stash it, and open
/// the WorkOS sign-in URL in the user's system browser (RFC 8252). Shared by the
/// `desktop_sign_in` IPC command (primary, invoked by the shell init-script) and
/// the `on_navigation` fallback. Returns the opened URL on success.
fn begin_desktop_sign_in(app: &tauri::AppHandle) -> Result<String, String> {
    let session = auth::new_pkce_session();
    let sign_in = auth::sign_in_url(&shell_origin(), &session)
        .map_err(|e| format!("failed to build sign-in url: {e}"))?;
    {
        let state = app.state::<AuthState>();
        let mut guard = state.0.lock().unwrap();
        *guard = Some(session);
    }
    use tauri_plugin_opener::OpenerExt;
    app.opener()
        .open_url(sign_in.clone(), None::<&str>)
        .map_err(|e| format!("failed to open system browser: {e}"))?;
    log::info!("opened system browser for desktop sign-in");
    Ok(sign_in)
}

/// IPC command the shell-injected script calls when the user clicks "Sign in".
/// This is the RELIABLE trigger: a Next.js `<Link>` click is a client-side RSC
/// navigation that `on_navigation` does not observe, so we drive the flow from an
/// explicit renderer→shell call (the same shape as the WorkOS Electron example).
#[tauri::command]
fn desktop_sign_in(app: tauri::AppHandle) -> Result<(), String> {
    begin_desktop_sign_in(&app).map(|_| ())
}

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
            None => {
                log::warn!("deep link auth callback failed validation (state mismatch?)")
            }
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
        // Custom UA so the BFF can detect the shell and relax CSP `connect-src`
        // to allow the Tauri IPC origin (otherwise the strict prod CSP blocks the
        // IPC fetch → `invoke` fails → sign-in dead). We keep a realistic macOS
        // Safari UA (so WorkOS/Next treat it as a normal browser) and append our
        // marker token that the middleware matches on.
        .user_agent(SHELL_USER_AGENT)
        // Shell-only init script (runs before page scripts in every frame; the
        // browser build never gets this). Two jobs:
        //   1. mark the document `html.tauri-shell` so the shared web build can
        //      opt into macOS chrome (traffic-light clearance) via CSS (§4b).
        //   2. capture-phase click delegation on any sign-in link → drive the
        //      system-browser flow via the `desktop_sign_in` IPC command. A
        //      Next.js `<Link>` click is a client-side RSC navigation that
        //      `on_navigation` never sees, so this is the reliable trigger.
        .initialization_script(SHELL_INIT_SCRIPT)
        .on_navigation(move |url| {
        let raw = url.as_str();
        // Full-page-navigation fallback for the sign-in flow (a hard load /
        // anchor to our web sign-in, or the cross-origin redirect to WorkOS's
        // authorize page). The PRIMARY trigger is the on_page_load eval below: a
        // Next `<Link>` click is an RSC navigation that never surfaces here.
        if auth::is_web_sign_in_nav(raw) || auth::is_workos_authorize_nav(raw) {
            if let Err(e) = begin_desktop_sign_in(&app_for_nav) {
                log::error!("desktop sign-in (nav intercept) failed: {e}");
            }
            return false; // cancel the in-webview navigation
        }
        true
    });

    // Attach the sign-in click handler via `eval` on every page load. Unlike
    // `initialization_script` (governed by the page's CSP, which on the deployed
    // app is strict nonce + 'strict-dynamic' and BLOCKS injected scripts), an
    // `eval` is executed by the webview host at the WebKit level and is NOT
    // subject to the page CSP. This is the reliable, CSP-proof trigger.
    let builder = builder.on_page_load(|window, _payload| {
        if let Err(e) = window.eval(SIGN_IN_CLICK_SCRIPT) {
            log::error!("failed to eval sign-in click handler: {e}");
        }
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
        .invoke_handler(tauri::generate_handler![desktop_sign_in])
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
