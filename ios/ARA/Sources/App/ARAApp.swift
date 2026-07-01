import FirebaseCore
import SwiftUI

@main
@MainActor
struct ARAApp: App {
    @State private var model = AppModel()

    init() {
        FirebaseBootstrap.configureIfAvailable()
    }

    var body: some Scene {
        WindowGroup {
            AppView(model: model)
        }
    }
}

private enum FirebaseBootstrap {
    static func configureIfAvailable() {
        guard FirebaseApp.app() == nil,
              let path = Bundle.main.path(
                forResource: "GoogleService-Info",
                ofType: "plist"
              ),
              let options = FirebaseOptions(contentsOfFile: path)
        else {
            return
        }

        FirebaseApp.configure(options: options)
    }
}
