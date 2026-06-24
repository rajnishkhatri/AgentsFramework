//! Desktop auth helpers (P5 Step 2) — pure, unit-testable, no Tauri deps.
//!
//! The shell owns the PKCE verifier (RFC 8252 — never dropped). This module
//! covers: generating the PKCE pair + a CSRF state nonce, building the
//! system-browser sign-in URL (carrying the S256 challenge), and rewriting the
//! custom-scheme deep-link return into the HTTPS desktop-callback navigation
//! the BFF expects.
//!
//! Design: docs/plans/p5_step2_auth_deeplink.design.md

use base64::Engine;
use rand::RngCore;
use sha2::{Digest, Sha256};
use url::Url;

/// The custom scheme the app registers; deep links arrive as `<SCHEME>://…`.
pub const SCHEME: &str = "agentsframework";

/// One in-flight sign-in: the verifier we keep + the state nonce we expect back.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PkceSession {
    pub verifier: String,
    pub challenge: String,
    pub state: String,
}

fn b64url(bytes: &[u8]) -> String {
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bytes)
}

/// Generate a fresh PKCE pair + state nonce. Verifier = 32 random bytes →
/// base64url (43 chars, within RFC 7636's 43–128). Challenge = base64url(SHA256).
pub fn new_pkce_session() -> PkceSession {
    let mut rng = rand::thread_rng();
    let mut vbytes = [0u8; 32];
    rng.fill_bytes(&mut vbytes);
    let verifier = b64url(&vbytes);

    let mut sbytes = [0u8; 16];
    rng.fill_bytes(&mut sbytes);
    let state = b64url(&sbytes);

    let challenge = challenge_for(&verifier);
    PkceSession { verifier, challenge, state }
}

/// S256 challenge for a verifier: base64url(SHA256(verifier_ascii)).
pub fn challenge_for(verifier: &str) -> String {
    let digest = Sha256::digest(verifier.as_bytes());
    b64url(&digest)
}

/// Build the system-browser sign-in URL against `origin`, carrying the desktop
/// client marker, the S256 `code_challenge`, and the `state` nonce.
pub fn sign_in_url(origin: &str, session: &PkceSession) -> Result<String, url::ParseError> {
    let mut url = Url::parse(origin)?;
    url.set_path("/api/auth/sign-in");
    url.query_pairs_mut()
        .clear()
        .append_pair("client", "desktop")
        .append_pair("code_challenge", &session.challenge)
        .append_pair("state", &session.state);
    Ok(url.into())
}

/// True when `url` is our auth deep link (`<SCHEME>://auth/callback…`).
pub fn is_auth_deep_link(url: &str) -> bool {
    Url::parse(url)
        .map(|u| u.scheme() == SCHEME && u.host_str() == Some("auth"))
        .unwrap_or(false)
}

/// True when a navigation target is the app's own web sign-in (which we
/// intercept and replace with the system-browser flow). Matches the
/// `/api/auth/sign-in` path WITHOUT an existing `client=desktop` marker (so the
/// browser leg we open ourselves is not re-intercepted).
pub fn is_web_sign_in_nav(url: &str) -> bool {
    match Url::parse(url) {
        Ok(u) => {
            u.path() == "/api/auth/sign-in"
                && !u.query_pairs().any(|(k, v)| k == "client" && v == "desktop")
        }
        Err(_) => false,
    }
}

/// True when the webview is about to load the WorkOS hosted-login (authorize)
/// page IN-WINDOW. This is the reliable intercept point: a Next `<Link>` click to
/// `/api/auth/sign-in` is handled as a client-side RSC navigation that
/// `on_navigation` never sees, but the resulting cross-origin redirect to
/// `api.workos.com/.../authorize` IS a real top-level navigation. We cancel it
/// and reopen our desktop sign-in (PKCE + custom-scheme redirect) in the system
/// browser. The browser leg's own authorize load happens OUTSIDE the webview, so
/// it is never seen here — no loop.
pub fn is_workos_authorize_nav(url: &str) -> bool {
    match Url::parse(url) {
        Ok(u) => {
            u.host_str() == Some("api.workos.com")
                && u.path().ends_with("/authorize")
                // Our own browser leg carries the custom-scheme redirect_uri; if
                // that ever shows up in-webview, don't re-intercept it.
                && !u.query_pairs().any(|(k, v)| {
                    k == "redirect_uri" && v.starts_with(&format!("{SCHEME}://"))
                })
        }
        Err(_) => false,
    }
}

/// Rewrite the deep-link return into the HTTPS desktop-callback navigation,
/// injecting the stashed `verifier`. Returns `None` if the deep link lacks the
/// expected `code`/`state`, or if `state` doesn't match the in-flight session
/// (CSRF guard — the verifier is only attached to a matching state).
pub fn callback_url(
    origin: &str,
    deep_link: &str,
    session: &PkceSession,
) -> Option<String> {
    let incoming = Url::parse(deep_link).ok()?;
    let mut code: Option<String> = None;
    let mut state: Option<String> = None;
    for (k, v) in incoming.query_pairs() {
        match k.as_ref() {
            "code" => code = Some(v.into_owned()),
            "state" => state = Some(v.into_owned()),
            _ => {}
        }
    }
    let code = code?;
    let state = state?;
    if state != session.state {
        return None; // state mismatch → reject (CSRF)
    }

    let mut url = Url::parse(origin).ok()?;
    url.set_path("/api/auth/desktop-callback");
    url.query_pairs_mut()
        .clear()
        .append_pair("code", &code)
        .append_pair("code_verifier", &session.verifier)
        .append_pair("state", &state);
    Some(url.into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pkce_pair_has_valid_shapes() {
        let s = new_pkce_session();
        // verifier 43 chars (32 bytes b64url no-pad), within RFC 7636 43..=128.
        assert_eq!(s.verifier.len(), 43);
        assert!(s.verifier.len() >= 43 && s.verifier.len() <= 128);
        // challenge is base64url(SHA256) = 43 chars.
        assert_eq!(s.challenge.len(), 43);
        // challenge actually derives from the verifier.
        assert_eq!(s.challenge, challenge_for(&s.verifier));
        // state nonce is non-trivial.
        assert!(s.state.len() >= 8);
    }

    #[test]
    fn pkce_sessions_are_unique() {
        let a = new_pkce_session();
        let b = new_pkce_session();
        assert_ne!(a.verifier, b.verifier);
        assert_ne!(a.state, b.state);
    }

    #[test]
    fn challenge_is_stable_and_known() {
        // RFC 7636 Appendix B test vector.
        let v = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
        assert_eq!(challenge_for(v), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
    }

    #[test]
    fn sign_in_url_carries_desktop_challenge_state() {
        let s = PkceSession {
            verifier: "v".repeat(43),
            challenge: "c".repeat(43),
            state: "statenonce".into(),
        };
        let url = sign_in_url("https://app.example.com", &s).unwrap();
        assert!(url.starts_with("https://app.example.com/api/auth/sign-in?"));
        assert!(url.contains("client=desktop"));
        assert!(url.contains(&format!("code_challenge={}", "c".repeat(43))));
        assert!(url.contains("state=statenonce"));
        // verifier MUST NOT appear in the sign-in URL (stays in the shell).
        assert!(!url.contains(&"v".repeat(43)));
    }

    #[test]
    fn detects_auth_deep_link() {
        assert!(is_auth_deep_link("agentsframework://auth/callback?code=x&state=y"));
        assert!(!is_auth_deep_link("agentsframework://other/path"));
        assert!(!is_auth_deep_link("https://app.example.com/api/auth/callback"));
        assert!(!is_auth_deep_link("not a url"));
    }

    #[test]
    fn detects_web_sign_in_nav_but_not_our_desktop_leg() {
        assert!(is_web_sign_in_nav("https://app.example.com/api/auth/sign-in"));
        assert!(is_web_sign_in_nav("https://app.example.com/api/auth/sign-in?returnTo=/x"));
        // our own desktop leg must NOT be re-intercepted.
        assert!(!is_web_sign_in_nav(
            "https://app.example.com/api/auth/sign-in?client=desktop&code_challenge=c&state=s"
        ));
        assert!(!is_web_sign_in_nav("https://app.example.com/chat"));
    }

    #[test]
    fn detects_workos_authorize_nav_but_not_our_browser_leg() {
        // The in-webview redirect to WorkOS (web flow) — intercept this.
        assert!(is_workos_authorize_nav(
            "https://api.workos.com/user_management/authorize?client_id=x&redirect_uri=https%3A%2F%2Fapp.example.com%2Fapi%2Fauth%2Fcallback"
        ));
        // Our own browser leg carries the custom-scheme redirect — must NOT be
        // re-intercepted (it loads outside the webview anyway, but guard it).
        assert!(!is_workos_authorize_nav(
            "https://api.workos.com/user_management/authorize?redirect_uri=agentsframework%3A%2F%2Fauth%2Fcallback&code_challenge=c"
        ));
        // Unrelated hosts/paths pass through.
        assert!(!is_workos_authorize_nav("https://app.example.com/chat"));
        assert!(!is_workos_authorize_nav("https://api.workos.com/user_management/token"));
        assert!(!is_workos_authorize_nav("not a url"));
    }

    #[test]
    fn callback_url_injects_verifier_on_state_match() {
        let s = PkceSession {
            verifier: "theverifier".repeat(4), // 44 chars, fine for the test
            challenge: "c".repeat(43),
            state: "statenonce".into(),
        };
        let out = callback_url(
            "https://app.example.com",
            "agentsframework://auth/callback?code=abc123&state=statenonce",
            &s,
        )
        .unwrap();
        assert!(out.starts_with("https://app.example.com/api/auth/desktop-callback?"));
        assert!(out.contains("code=abc123"));
        assert!(out.contains(&format!("code_verifier={}", "theverifier".repeat(4))));
        assert!(out.contains("state=statenonce"));
    }

    #[test]
    fn callback_url_rejects_state_mismatch() {
        let s = PkceSession {
            verifier: "v".repeat(43),
            challenge: "c".repeat(43),
            state: "expected".into(),
        };
        let out = callback_url(
            "https://app.example.com",
            "agentsframework://auth/callback?code=abc&state=ATTACKER",
            &s,
        );
        assert!(out.is_none());
    }

    #[test]
    fn callback_url_rejects_missing_code() {
        let s = PkceSession {
            verifier: "v".repeat(43),
            challenge: "c".repeat(43),
            state: "statenonce".into(),
        };
        let out = callback_url(
            "https://app.example.com",
            "agentsframework://auth/callback?state=statenonce",
            &s,
        );
        assert!(out.is_none());
    }
}
