import Foundation
import FoundationModels

// Usage: armstest <passages.json> <runs> <out.jsonl>
let args = CommandLine.arguments
let passagesURL = URL(fileURLWithPath: args[1])
let runs = Int(args[2]) ?? 1
let outURL = URL(fileURLWithPath: args[3])

struct Passage: Decodable { let id: String; let instructions: String; let text: String; let maxTokens: Int? }

let passages = try JSONDecoder().decode([Passage].self, from: Data(contentsOf: passagesURL))
FileManager.default.createFile(atPath: outURL.path, contents: nil)
let handle = try FileHandle(forWritingTo: outURL)
let model = SystemLanguageModel(guardrails: .permissiveContentTransformations)
print("contextSize:", SystemLanguageModel.default.contextSize)

for run in 0..<runs {
    let ordered = run % 2 == 0 ? passages : passages.reversed()
    for passage in ordered {
        let session = LanguageModelSession(model: model, instructions: passage.instructions)
        let started = Date()
        var record: [String: Any] = ["id": passage.id, "run": run]
        do {
            let response = try await session.respond(
                to: passage.text,
                options: GenerationOptions(maximumResponseTokens: passage.maxTokens ?? 220)
            )
            record["outcome"] = "success"
            record["text"] = response.content
        } catch {
            record["outcome"] = "error"
            record["error"] = String(String(describing: error).prefix(300))
        }
        record["secs"] = (Date().timeIntervalSince(started) * 10).rounded() / 10
        try handle.write(contentsOf: try JSONSerialization.data(withJSONObject: record) + Data("\n".utf8))
        print(passage.id, run, record["outcome"] ?? "", record["secs"] ?? "")
        fflush(stdout)
    }
}
try handle.close()
