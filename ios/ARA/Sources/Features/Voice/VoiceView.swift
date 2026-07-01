import SwiftUI

struct VoiceView: View {
    private let araNumber = "+16196394611"

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "waveform.circle.fill")
                .font(.system(size: 86))
                .foregroundStyle(.indigo)

            VStack(spacing: 8) {
                Text("ARA Voice")
                    .font(.title.bold())
                Text("Call the verified LiveKit voice line. In-app voice is the next connection after this first build is compiled.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
            }

            Link(destination: URL(string: "tel://\(araNumber)")!) {
                Label("Call (619) 639-4611", systemImage: "phone.fill")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .foregroundStyle(.white)
                    .background(.indigo)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }
        }
        .padding(24)
        .navigationTitle("Voice")
    }
}
