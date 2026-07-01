# Conductor iOS app — scaffold

This is a starting point for a native iOS client, written to mirror the
navy-blue web UI in `api/static/` and to use Apple's 2026 Foundation Models
framework (on-device or server-model routing) plus App Intents for Siri.

## This cannot be built or tested in the environment that generated it

This source was written in a Linux container with no Xcode, no macOS, and
no iOS Simulator. SwiftUI, App Intents, and the Foundation Models framework
are Apple-platform-only APIs — nothing here has been compiled, run, or
visually verified. Treat this as a real, complete first draft that needs a
build/fix/test pass on a Mac before it's demo-able, let alone submittable
to the App Store.

## Opening this in Xcode

The files under `Sources/ConductorApp/` are plain Swift — no project-specific
magic. The fastest path to a running app:

1. In Xcode: **File → New → Project → iOS → App**. Name it `Conductor`,
   interface: SwiftUI, language: Swift.
2. Delete the generated `ContentView.swift`/`ConductorApp.swift` (or replace
   their contents).
3. Drag the `Views/`, `Networking/`, `Intelligence/`, and `Intents/` folders
   from this directory into the new project (checking "Copy items if
   needed").
4. Add microphone usage description to the generated `Info.plist` (see
   `Resources/Info.plist` here for the key/value to copy in) — required for
   voice input, App Store review will reject without it.
5. Set the backend URL: `ConductorClient` defaults to
   `http://localhost:8080` — point it at your deployed Cloud
   Run/Render URL for anything beyond local testing.
6. Build and run on a Simulator or device running iOS 18+.

## What's real vs. what needs design work on a Mac

- `Networking/ConductorClient.swift` talks to this repo's actual, already-
  working endpoints (`/api/chat`, `/api/voice-chat`, `/health`) — no backend
  changes needed.
- `Views/ChatView.swift` mirrors the sidebar+chat layout and navy palette
  from `api/static/style.css`, translated to SwiftUI. Layout will need real
  device/simulator iteration — nothing here has been visually checked.
- `Intelligence/ConductorLanguageModel.swift` sketches Apple's provider-
  bridging pattern from the WWDC26 "Bring an LLM provider to the Foundation
  Models framework" session — routing a prompt to either the on-device
  model or this app's backend. The exact `LanguageModel` protocol
  requirements should be checked against the current framework docs in
  Xcode (protocol shapes shift between betas); this is a best-effort sketch,
  not a verified conformance.
- `Intents/AskConductorIntent.swift` sketches an `AppIntent` for Siri/
  Shortcuts — again, unverified against a real build.

## Before App Store submission

- Real device testing (voice/mic permissions behave differently in
  Simulator).
- An Apple Developer account, App Store Connect listing, and signing/
  provisioning setup — none of that is scaffolded here since it's account-
  specific and can't be done from source alone.
- A privacy policy covering voice data and any third-party LLM provider
  calls, since this app sends user speech/text to external APIs
  (OpenAI/Anthropic/Google/xAI) via the backend.
