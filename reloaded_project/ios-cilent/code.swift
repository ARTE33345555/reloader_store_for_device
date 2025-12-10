// iOS/PackageModels.swift
import Foundation

struct Package: Identifiable, Codable, Hashable {
    var id: String { name + ":" + version }
    let name: String
    let version: String
    let category: String
    let description: String?
    let downloadURL: URL
    let sha256: String?
    let sizeBytes: Int?
}
