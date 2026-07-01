import SwiftUI

struct ChatView: View {
    let model: AppModel
    @State private var draft = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(model.messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: model.messages) {
                    guard let last = model.messages.last else { return }
                    withAnimation {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }

            if let error = model.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)
            }

            HStack(alignment: .bottom, spacing: 10) {
                TextField("Message the Council", text: $draft, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...5)
                    .submitLabel(.send)
                    .onSubmit(send)

                Button(action: send) {
                    if model.isSending {
                        ProgressView()
                    } else {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.title)
                    }
                }
                .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.isSending)
                .accessibilityLabel("Send message")
            }
            .padding()
            .background(.regularMaterial)
        }
        .navigationTitle("ARA Council")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func send() {
        let message = draft
        draft = ""
        Task {
            await model.send(message)
        }
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .assistant {
                bubble
                Spacer(minLength: 42)
            } else {
                Spacer(minLength: 42)
                bubble
            }
        }
    }

    private var bubble: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(message.text)
                .textSelection(.enabled)

            if !message.evidence.isEmpty {
                Text("\(message.evidence.count) evidence item\(message.evidence.count == 1 ? "" : "s")")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(
            message.role == .assistant
                ? Color(.secondarySystemBackground)
                : Color.indigo
        )
        .foregroundColor(message.role == .assistant ? .primary : .white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}
