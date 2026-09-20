import Foundation
import Vision

// Emit recognized lines with image-normalized boxes, using the local Vision runtime.
let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en-US"]
request.usesLanguageCorrection = false
request.minimumTextHeight = 0.002
let handler = VNImageRequestHandler(url: inputURL, options: [:])
try handler.perform([request])
let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    let box = observation.boundingBox
    return ["text": candidate.string, "confidence": candidate.confidence,
            "left": box.minX, "top": 1 - box.maxY,
            "width": box.width, "height": box.height]
}
let result: [String: Any] = ["revision": request.revision,
    "os_version": ProcessInfo.processInfo.operatingSystemVersionString,
    "recognition_level": "accurate", "language_correction": false,
    "lines": rows]
let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
