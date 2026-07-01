import SwiftUI

/// App entry point. Move this file's contents into the `@main` struct that
/// Xcode generates for a new iOS App project (see README.md) — a plain
/// SwiftPM library target can't declare `@main` for an iOS app bundle.
public struct ConductorApp: App {
    public init() {}

    public var body: some Scene {
        WindowGroup {
            ChatView()
                .preferredColorScheme(.dark)
        }
    }
}
