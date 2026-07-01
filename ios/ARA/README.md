# ARA iOS

Native SwiftUI front end for the deployed OpenAI-led Conductor Council.

## Verified service targets

- Bundle ID: `com.cramerconsulting.conductoragent`
- Firebase project: `conductor-agent`
- Conductor API: `https://conductor-agent-396823428450.us-central1.run.app`
- Voice line: `+1 619-639-4611`

No model-provider API keys belong in this app. The app calls the Cloud Run
service, which owns provider credentials and Council routing.

## Generate the Xcode project

1. Install a current Xcode release.
2. Install XcodeGen: `brew install xcodegen`
3. From this directory, run `zsh fetch-firebase-config.sh`.
4. Run `xcodegen generate`.
5. Open `ARA.xcodeproj`.
6. Select the Cramer Consulting Group development team under Signing.

`Configuration/GoogleService-Info.plist` is intentionally ignored by Git. A
local copy can be downloaded from the existing Firebase iOS app registration.
The app remains usable without that file; Firebase initializes only when the
configuration is present.
