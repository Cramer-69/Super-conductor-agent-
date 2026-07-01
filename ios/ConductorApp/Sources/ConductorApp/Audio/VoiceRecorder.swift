import AVFoundation
import SwiftUI

/// Records a short voice clip to a temp file and hands the raw data back —
/// pairs with ConductorClient.voiceChat(audioData:). Needs
/// NSMicrophoneUsageDescription in Info.plist (see Resources/Info.plist).
@MainActor
final class VoiceRecorder: NSObject, ObservableObject {
    @Published var isRecording = false
    @Published var lastError: String?

    var onFinishedRecording: ((Data) -> Void)?

    private var recorder: AVAudioRecorder?
    private var fileURL: URL?

    func toggle() {
        if isRecording {
            stop()
        } else {
            Task { await start() }
        }
    }

    private func start() async {
        let session = AVAudioSession.sharedInstance()
        do {
            let granted = await requestPermission(session: session)
            guard granted else {
                lastError = "Microphone access denied. Enable it in Settings."
                return
            }

            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)

            let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID()).m4a")
            let settings: [String: Any] = [
                AVFormatIDKey: kAudioFormatMPEG4AAC,
                AVSampleRateKey: 44_100,
                AVNumberOfChannelsKey: 1,
                AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
            ]

            let recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder.record()

            self.recorder = recorder
            self.fileURL = url
            self.isRecording = true
        } catch {
            lastError = "Could not start recording: \(error.localizedDescription)"
        }
    }

    private func stop() {
        recorder?.stop()
        isRecording = false

        guard let fileURL, let data = try? Data(contentsOf: fileURL) else { return }
        onFinishedRecording?(data)
        try? FileManager.default.removeItem(at: fileURL)
    }

    private func requestPermission(session: AVAudioSession) async -> Bool {
        await withCheckedContinuation { continuation in
            session.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }
}
