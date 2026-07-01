import SwiftUI

struct VoiceView: View {
    @State private var model = VoiceModel()
    private let araNumber = "+16196394611"

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "waveform.circle.fill")
                .font(.system(size: 86))
                .foregroundStyle(.indigo)

            VStack(spacing: 8) {
                Text("ARA Voice")
                    .font(.title.bold())
                Text(statusText)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
            }

            Button {
                Task {
                    if model.isConnected {
                        await model.disconnect()
                    } else {
                        await model.connect()
                    }
                }
            } label: {
                Label(
                    model.isConnected ? "End ARA Session" : "Talk with ARA",
                    systemImage: model.isConnected
                        ? "phone.down.fill"
                        : "mic.fill"
                )
                .font(.headline)
                .frame(maxWidth: .infinity)
                .padding()
                .foregroundStyle(.white)
                .background(model.isConnected ? Color.red : Color.indigo)
                .clipShape(RoundedRectangle(cornerRadius: 14))
            }
            .disabled(model.state == .connecting)

            if model.state == .connecting {
                ProgressView("Connecting securely…")
            }

            Link(destination: URL(string: "tel://\(araNumber)")!) {
                Label("Telephone fallback", systemImage: "phone")
            }
        }
        .padding(24)
        .navigationTitle("Voice")
        .onDisappear {
            Task {
                await model.disconnect()
            }
        }
    }

    private var statusText: String {
        switch model.state {
        case .idle:
            return "Start a private in-app conversation with ARA."
        case .connecting:
            return "Authenticating and bringing ARA into the room."
        case .connected:
            return "ARA is connected and listening."
        case let .failed(message):
            return message
        }
    }
}
