// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "ConductorApp",
    platforms: [.iOS(.v18)],
    products: [
        .library(name: "ConductorApp", targets: ["ConductorApp"])
    ],
    targets: [
        .target(name: "ConductorApp")
    ]
)
