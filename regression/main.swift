import Foundation
import FoundationModels

// Usage: guardtest <passages.json> <modes: default,permissive> <runs> <out.jsonl>
let args = CommandLine.arguments
let passagesURL = URL(fileURLWithPath: args[1])
let modes = args[2].split(separator: ",").map(String.init)
let runs = Int(args[3]) ?? 1
let outURL = URL(fileURLWithPath: args[4])

struct Passage: Decodable { let id: String; let text: String }

let instructions = """
You are a voice audiobook assistant.
Give a detailed, natural spoken recap of what the listener missed and nothing else, limited to 2-4 sentences.
"""

func model(for mode: String) -> SystemLanguageModel {
    mode == "permissive"
        ? SystemLanguageModel(guardrails: .permissiveContentTransformations)
        : SystemLanguageModel(guardrails: .default)
}

func classify(_ error: Error) -> String {
    if let e = error as? LanguageModelSession.GenerationError {
        switch e {
        case .guardrailViolation: return "guardrail"
        case .refusal: return "refusal_error"
        case .exceededContextWindowSize: return "context_overflow"
        case .rateLimited: return "rate_limited"
        case .assetsUnavailable: return "assets_unavailable"
        case .unsupportedLanguageOrLocale: return "unsupported_language"
        case .decodingFailure: return "decoding"
        default: return "other_generation_error"
        }
    }
    return "other:\(type(of: error))"
}

let passages = try JSONDecoder().decode([Passage].self, from: Data(contentsOf: passagesURL))
FileManager.default.createFile(atPath: outURL.path, contents: nil)
let handle = try FileHandle(forWritingTo: outURL)

print("availability:", SystemLanguageModel.default.availability, "contextSize:", SystemLanguageModel.default.contextSize)

for passage in passages {
    for run in 0..<runs {
        let ordered = run % 2 == 0 ? modes : modes.reversed()
        for mode in ordered {
            let session = LanguageModelSession(model: model(for: mode), instructions: instructions)
            let started = Date()
            var record: [String: Any] = ["id": passage.id, "mode": mode, "run": run]
            do {
                let response = try await session.respond(
                    to: passage.text,
                    options: GenerationOptions(maximumResponseTokens: 220)
                )
                record["outcome"] = "success"
                record["text"] = response.content
            } catch {
                record["outcome"] = classify(error)
                record["error"] = String(String(describing: error).prefix(300))
            }
            record["secs"] = (Date().timeIntervalSince(started) * 10).rounded() / 10
            try handle.write(contentsOf: try JSONSerialization.data(withJSONObject: record) + Data("\n".utf8))
            print(passage.id, mode, run, record["outcome"] ?? "", record["secs"] ?? "")
            fflush(stdout)
        }
    }
}
try handle.close()
