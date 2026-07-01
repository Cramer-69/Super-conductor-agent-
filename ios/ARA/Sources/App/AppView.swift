import SwiftUI

struct AppView: View {
    let model: AppModel

    var body: some View {
        TabView {
            NavigationStack {
                ChatView(model: model)
            }
            .tabItem {
                Label("Council", systemImage: "sparkles")
            }

            NavigationStack {
                VoiceView()
            }
            .tabItem {
                Label("Voice", systemImage: "waveform")
            }

            NavigationStack {
                StatusView(model: model)
            }
            .tabItem {
                Label("Status", systemImage: "checkmark.shield")
            }
        }
        .tint(.indigo)
    }
}
