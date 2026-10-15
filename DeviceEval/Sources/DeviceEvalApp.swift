import FoundationModels
import SwiftUI

@main
struct DeviceEvalApp: App {
    var body: some Scene {
        WindowGroup {
            RunnerView()
        }
    }
}

struct Job: Decodable, Sendable {
    let id: String
    let instructions: String
    let text: String
}

@MainActor
@Observable
final class Runner {
    static let runs = 3

    var status = "Idle"
    var completed = 0
    var total = 0
    var isRunning = false

    private let resultsURL = URL.documentsDirectory.appending(path: "results.jsonl")

    var modelSummary: String {
        let model = SystemLanguageModel.default
        return "availability: \(model.availability) · contextSize: \(model.contextSize)"
    }

    func start() {
        guard !isRunning else { return }
        isRunning = true
        UIApplication.shared.isIdleTimerDisabled = true
        Task {
            await runAll()
            UIApplication.shared.isIdleTimerDisabled = false
            isRunning = false
        }
    }

    private func runAll() async {
        guard let url = Bundle.main.url(forResource: "device_jobs", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let jobs = try? JSONDecoder().decode([Job].self, from: data) else {
            status = "Could not load device_jobs.json"
            return
        }
        let done = alreadyDone()
        total = jobs.count * Self.runs
        completed = done.count
        let model = SystemLanguageModel(guardrails: .permissiveContentTransformations)

        for run in 0..<Self.runs {
            let ordered = run.isMultiple(of: 2) ? jobs : jobs.reversed()
            for job in ordered where !done.contains("\(job.id)#\(run)") {
                status = "Run \(run + 1): \(job.id)"
                let session = LanguageModelSession(model: model, instructions: job.instructions)
                let started = Date()
                var record: [String: Any] = ["id": job.id, "run": run]
                do {
                    let response = try await session.respond(
                        to: job.text,
                        options: GenerationOptions(maximumResponseTokens: 220)
                    )
                    record["outcome"] = "success"
                    record["text"] = response.content
                } catch {
                    record["outcome"] = "error"
                    record["error"] = String(String(describing: error).prefix(300))
                }
                record["secs"] = (Date().timeIntervalSince(started) * 10).rounded() / 10
                append(record)
                completed += 1
            }
        }
        status = "Finished \(completed)/\(total)"
    }

    private func alreadyDone() -> Set<String> {
        guard let text = try? String(contentsOf: resultsURL, encoding: .utf8) else { return [] }
        var keys = Set<String>()
        for line in text.split(separator: "\n") {
            guard let object = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any],
                  let id = object["id"] as? String,
                  let run = object["run"] as? Int else { continue }
            keys.insert("\(id)#\(run)")
        }
        return keys
    }

    private func append(_ record: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: record) else { return }
        let line = data + Data("\n".utf8)
        if let handle = try? FileHandle(forWritingTo: resultsURL) {
            handle.seekToEndOfFile()
            handle.write(line)
            try? handle.close()
        } else {
            try? line.write(to: resultsURL)
        }
    }
}

struct RunnerView: View {
    @State private var runner = Runner()

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("WDIM device eval").font(.title2.bold())
            Text(runner.modelSummary).font(.footnote).foregroundStyle(.secondary)
            ProgressView(value: Double(runner.completed), total: Double(max(runner.total, 1)))
            Text("\(runner.completed) / \(runner.total)").monospacedDigit()
            Text(runner.status).font(.footnote).lineLimit(3)
            Button(runner.isRunning ? "Running…" : "Start") { runner.start() }
                .buttonStyle(.borderedProminent)
                .disabled(runner.isRunning)
            Text("Keep the app open and the phone unlocked until it finishes.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
        .task {
            if ProcessInfo.processInfo.arguments.contains("--autorun") {
                runner.start()
            }
        }
    }
}
