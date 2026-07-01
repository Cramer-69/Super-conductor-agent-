import SwiftUI

/// Navy-blue palette mirroring api/static/style.css, so the web and iOS
/// clients read as one product.
enum ConductorTheme {
    private static func rgb(_ r: Int, _ g: Int, _ b: Int) -> Color {
        Color(red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255)
    }

    static let background = rgb(0x0b, 0x11, 0x20)
    static let elevated = rgb(0x11, 0x1a, 0x2e)
    static let sidebar = rgb(0x0d, 0x14, 0x24)
    static let accent = rgb(0x2d, 0xd4, 0xbf)
    static let accentStrong = rgb(0x14, 0xb8, 0xa6)
    static let textDim = Color.white.opacity(0.65)
    static let textFaint = Color.white.opacity(0.4)
}

struct ChatMessage: Identifiable {
    enum Role { case user, assistant, system }
    let id = UUID()
    let role: Role
    let text: String
}

@MainActor
final class ConductorChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var draft: String = ""
    @Published var statusText: String = "Type a message or tap the mic to talk"
    @Published var isSending = false
    @Published var health: ConductorHealth?

    private let client = ConductorClient()

    func loadHealth() async {
        health = try? await client.health()
    }

    func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        messages.append(ChatMessage(role: .user, text: text))
        draft = ""
        statusText = "Thinking..."
        isSending = true
        defer { isSending = false }

        do {
            let response = try await client.chat(query: text)
            messages.append(ChatMessage(role: .assistant, text: response.response))
            if let firstSource = response.sources.first {
                messages.append(
                    ChatMessage(role: .system, text: "📚 \(firstSource.platform.uppercased()): \(firstSource.title)")
                )
            }
            statusText = "Type a message or tap the mic to talk"
        } catch {
            statusText = "Error: \(error.localizedDescription)"
        }
    }

    func newChat() {
        messages.removeAll()
        statusText = "Type a message or tap the mic to talk"
    }

    func sendVoiceClip(_ audioData: Data) async {
        messages.append(ChatMessage(role: .user, text: "🎤 Voice message..."))
        statusText = "Processing..."
        isSending = true
        defer { isSending = false }

        do {
            let response = try await client.voiceChat(audioData: audioData)
            messages.append(ChatMessage(role: .assistant, text: response.response))
            statusText = "Type a message or tap the mic to talk"
        } catch {
            statusText = "Error: \(error.localizedDescription)"
        }
    }
}

struct ChatView: View {
    @StateObject private var viewModel = ConductorChatViewModel()
    @State private var sidebarVisibility: NavigationSplitViewVisibility = .automatic

    var body: some View {
        NavigationSplitView(columnVisibility: $sidebarVisibility) {
            SidebarView(viewModel: viewModel)
        } detail: {
            ConversationView(viewModel: viewModel)
        }
        .task {
            await viewModel.loadHealth()
        }
    }
}

private struct SidebarView: View {
    @ObservedObject var viewModel: ConductorChatViewModel

    var body: some View {
        List {
            Button {
                viewModel.newChat()
            } label: {
                Label("New chat", systemImage: "plus")
            }

            Section("History") {
                Text("No conversation history yet")
                    .foregroundStyle(ConductorTheme.textFaint)
                    .font(.footnote)
            }

            if let health = viewModel.health {
                Section("Status") {
                    statusRow("LLM", isOn: !health.providers.isEmpty, detail: health.providers.joined(separator: ", "))
                    statusRow("Voice", isOn: health.voiceConfigured)
                    ForEach(health.connectors.sorted(by: { $0.key < $1.key }), id: \.key) { name, isOn in
                        statusRow(name, isOn: isOn)
                    }
                }
            }
        }
        .navigationTitle("Conductor")
        .scrollContentBackground(.hidden)
        .background(ConductorTheme.sidebar)
    }

    private func statusRow(_ label: String, isOn: Bool, detail: String? = nil) -> some View {
        HStack {
            Circle()
                .fill(isOn ? ConductorTheme.accent : Color.gray)
                .frame(width: 8, height: 8)
            Text(detail.map { "\(label): \($0)" } ?? label)
                .font(.caption)
                .foregroundStyle(ConductorTheme.textDim)
        }
    }
}

private struct ConversationView: View {
    @ObservedObject var viewModel: ConductorChatViewModel
    @FocusState private var inputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        if viewModel.messages.isEmpty {
                            EmptyStateView()
                        }
                        ForEach(viewModel.messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }
                    .padding(16)
                }
                .onChange(of: viewModel.messages.count) { _, _ in
                    if let last = viewModel.messages.last {
                        withAnimation {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }

            Text(viewModel.statusText)
                .font(.caption)
                .foregroundStyle(ConductorTheme.textFaint)
                .padding(.bottom, 4)

            ComposerView(viewModel: viewModel, inputFocused: $inputFocused)
        }
        .background(ConductorTheme.background)
    }
}

private struct EmptyStateView: View {
    var body: some View {
        VStack(spacing: 8) {
            Text("👋 Hi there!")
                .font(.title2)
            Text("Type a message or tap the mic to start talking")
                .font(.subheadline)
                .foregroundStyle(ConductorTheme.textFaint)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 80)
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 40) }
            Text(message.text)
                .font(message.role == .system ? .caption : .subheadline)
                .padding(12)
                .background(background)
                .foregroundStyle(message.role == .user ? Color.black.opacity(0.85) : Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 14))
            if message.role != .user { Spacer(minLength: 40) }
        }
    }

    private var background: Color {
        switch message.role {
        case .user: return ConductorTheme.accentStrong
        case .assistant: return ConductorTheme.elevated
        case .system: return .clear
        }
    }
}

private struct ComposerView: View {
    @ObservedObject var viewModel: ConductorChatViewModel
    var inputFocused: FocusState<Bool>.Binding
    @StateObject private var recorder = VoiceRecorder()

    var body: some View {
        HStack(spacing: 8) {
            TextField("Message Conductor...", text: $viewModel.draft, axis: .vertical)
                .focused(inputFocused)
                .textFieldStyle(.plain)
                .padding(.vertical, 8)

            Button {
                recorder.toggle()
            } label: {
                Image(systemName: recorder.isRecording ? "waveform" : "mic.fill")
                    .frame(width: 40, height: 40)
                    .background(recorder.isRecording ? Color.red : ConductorTheme.accentStrong)
                    .foregroundStyle(.black)
                    .clipShape(Circle())
            }

            Button("Send") {
                Task { await viewModel.send() }
            }
            .buttonStyle(.borderedProminent)
            .tint(ConductorTheme.accentStrong)
            .disabled(viewModel.draft.trimmingCharacters(in: .whitespaces).isEmpty || viewModel.isSending)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(ConductorTheme.elevated)
        .clipShape(RoundedRectangle(cornerRadius: 28))
        .padding(16)
        .onSubmit {
            Task { await viewModel.send() }
        }
        .task {
            recorder.onFinishedRecording = { audioData in
                Task { await viewModel.sendVoiceClip(audioData) }
            }
        }
    }
}
