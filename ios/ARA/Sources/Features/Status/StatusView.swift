import SwiftUI

struct StatusView: View {
    let model: AppModel

    var body: some View {
        List {
            Section("Conductor") {
                statusRow("Service", value: model.health?.status ?? "Checking…")
                statusRow("Build", value: model.health?.buildID ?? "—")
                statusRow("Lead", value: model.health?.leadProvider ?? "—")
                statusRow("Model", value: model.health?.activeModel ?? "—")
            }

            Section("Council") {
                ForEach(model.health?.providers ?? [], id: \.self) { provider in
                    Label(provider.capitalized, systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                }
            }

            Section("Capabilities") {
                ForEach(model.health?.capabilities ?? [], id: \.self) { capability in
                    Text(capability.replacingOccurrences(of: "_", with: " ").capitalized)
                }
            }

            if let error = model.errorMessage {
                Section("Connection error") {
                    Text(error)
                        .foregroundStyle(.red)
                }
            }
        }
        .navigationTitle("Verified Status")
        .refreshable {
            await model.refreshHealth()
        }
        .task {
            await model.refreshHealth()
        }
        .overlay {
            if model.isCheckingHealth && model.health == nil {
                ProgressView("Verifying Conductor…")
            }
        }
    }

    @ViewBuilder
    private func statusRow(_ title: String, value: String) -> some View {
        LabeledContent(title, value: value)
    }
}
