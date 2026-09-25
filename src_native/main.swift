import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var pythonProcess: Process?
    var serverPort: Int = 8080

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)

        let bundlePath = Bundle.main.bundlePath
        let projectDir = findProjectDirectory(bundlePath: bundlePath)

        serverPort = findFreePort(startingAt: 8080)
        startBackendServer(projectDir: projectDir, port: serverPort)

        setupWindow()
        setupMenuBar()

        if let url = URL(string: "http://127.0.0.1:\(serverPort)") {
            waitForServerReady(url: url, maxAttempts: 50) { [weak self] success in
                DispatchQueue.main.async {
                    if success {
                        self?.webView.load(URLRequest(url: url))
                    } else {
                        self?.showErrorAlert("Failed to start local Erowid SafeDB engine.")
                    }
                }
            }
        }

        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationWillTerminate(_ notification: Notification) {
        if let proc = pythonProcess, proc.isRunning {
            proc.terminate()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    // MARK: - Project Directory & Process Management

    func findProjectDirectory(bundlePath: String) -> String {
        if let envDir = ProcessInfo.processInfo.environment["EROWID_PROJECT_DIR"],
           FileManager.default.fileExists(atPath: envDir) {
            return envDir
        }
        let standardPath = "/Users/marksadler/erowid_safedb"
        if FileManager.default.fileExists(atPath: standardPath) {
            return standardPath
        }
        let parentDir = (bundlePath as NSString).deletingLastPathComponent
        let adjacentDir = (parentDir as NSString).appendingPathComponent("erowid_safedb")
        if FileManager.default.fileExists(atPath: adjacentDir) {
            return adjacentDir
        }
        return standardPath
    }

    func findFreePort(startingAt startPort: Int) -> Int {
        for port in startPort..<(startPort + 30) {
            var addr = sockaddr_in()
            addr.sin_len = __uint8_t(MemoryLayout<sockaddr_in>.size)
            addr.sin_family = sa_family_t(AF_INET)
            addr.sin_port = in_port_t(port).bigEndian
            addr.sin_addr.s_addr = inet_addr("127.0.0.1")

            let sock = socket(AF_INET, SOCK_STREAM, 0)
            if sock < 0 { continue }
            defer { close(sock) }

            let result = withUnsafePointer(to: &addr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    connect(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
            if result != 0 {
                return port // Port is not in use
            }
        }
        return startPort
    }

    func startBackendServer(projectDir: String, port: Int) {
        // If an instance is already listening on this port, don't spawn another
        if isPortListening(port: port) {
            return
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        proc.currentDirectoryURL = URL(fileURLWithPath: projectDir)
        proc.arguments = ["gui.py", "--server-only", "--port", "\(port)"]

        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/Library/Developer/CommandLineTools/usr/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + (env["PATH"] ?? "")
        env["PYTHONPATH"] = "/Users/marksadler/Library/Python/3.9/lib/python/site-packages:\(projectDir):" + (env["PYTHONPATH"] ?? "")
        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        do {
            try proc.run()
            self.pythonProcess = proc
        } catch {
            print("Failed to spawn Python backend: \(error)")
        }
    }

    func isPortListening(port: Int) -> Bool {
        var addr = sockaddr_in()
        addr.sin_len = __uint8_t(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")

        let sock = socket(AF_INET, SOCK_STREAM, 0)
        if sock < 0 { return false }
        defer { close(sock) }

        let result = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                connect(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return result == 0
    }

    func waitForServerReady(url: URL, maxAttempts: Int, attempt: Int = 0, completion: @escaping (Bool) -> Void) {
        if attempt >= maxAttempts {
            completion(false)
            return
        }

        var request = URLRequest(url: URL(string: "\(url.absoluteString)/api/stats")!)
        request.timeoutInterval = 0.5

        let task = URLSession.shared.dataTask(with: request) { [weak self] _, response, error in
            if let http = response as? HTTPURLResponse, http.statusCode == 200 {
                completion(true)
            } else {
                DispatchQueue.global().asyncAfter(deadline: .now() + 0.06) {
                    self?.waitForServerReady(url: url, maxAttempts: maxAttempts, attempt: attempt + 1, completion: completion)
                }
            }
        }
        task.resume()
    }

    // MARK: - Window Setup

    func setupWindow() {
        let screenRect = NSScreen.main?.visibleFrame ?? NSRect(x: 100, y: 100, width: 1200, height: 800)
        let width: CGFloat = min(1200, screenRect.width * 0.9)
        let height: CGFloat = min(820, screenRect.height * 0.9)
        let rect = NSRect(x: (screenRect.width - width) / 2 + screenRect.minX,
                          y: (screenRect.height - height) / 2 + screenRect.minY,
                          width: width, height: height)

        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )

        window.title = "Erowid SafeDB - Harm Reduction & Universal Archive"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = NSColor(red: 9/255, green: 13/255, blue: 22/255, alpha: 1.0)
        window.minSize = NSSize(width: 900, height: 600)
        window.delegate = self

        // Configure WKWebView
        let config = WKWebViewConfiguration()
        let prefs = WKWebpagePreferences()
        prefs.allowsContentJavaScript = true
        config.defaultWebpagePreferences = prefs

        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground") // Transparent background
        if #available(macOS 12.0, *) {
            webView.underPageBackgroundColor = NSColor(red: 9/255, green: 13/255, blue: 22/255, alpha: 1.0)
        }

        window.contentView!.addSubview(webView)
        window.makeKeyAndOrderFront(nil)
    }

    // MARK: - Menu Bar Setup

    func setupMenuBar() {
        let mainMenu = NSMenu()

        // 1. App Menu
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About Erowid SafeDB", action: #selector(showAbout), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Hide Erowid SafeDB", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = NSMenuItem(title: "Hide Others", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(hideOthers)
        appMenu.addItem(withTitle: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit Erowid SafeDB", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)

        // 2. Navigation Menu
        let navMenuItem = NSMenuItem()
        let navMenu = NSMenu(title: "Navigation")
        navMenu.addItem(withTitle: "💊 Dossiers & Dosage Ladder", action: #selector(navDossiers), keyEquivalent: "1")
        navMenu.addItem(withTitle: "⚡ Combo Risk Radar", action: #selector(navRadar), keyEquivalent: "2")
        navMenu.addItem(withTitle: "📚 Master Catalog (560+)", action: #selector(navCatalog), keyEquivalent: "3")
        navMenu.addItem(withTitle: "📖 Experience Vault", action: #selector(navVault), keyEquivalent: "4")
        navMenu.addItem(withTitle: "🧪 Reagents & Test Strips", action: #selector(navReagents), keyEquivalent: "5")
        navMenu.addItem(withTitle: "📥 Archive Harvester", action: #selector(navHarvester), keyEquivalent: "6")
        navMenu.addItem(NSMenuItem.separator())
        let emergencyItem = NSMenuItem(title: "🚨 Emergency Overdose Protocol", action: #selector(navEmergency), keyEquivalent: "e")
        emergencyItem.keyEquivalentModifierMask = [.command]
        navMenu.addItem(emergencyItem)
        navMenuItem.submenu = navMenu
        mainMenu.addItem(navMenuItem)

        // 3. Edit Menu (Standard macOS keyboard shortcuts)
        let editMenuItem = NSMenuItem()
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editMenuItem.submenu = editMenu
        mainMenu.addItem(editMenuItem)

        // 4. View Menu
        let viewMenuItem = NSMenuItem()
        let viewMenu = NSMenu(title: "View")
        viewMenu.addItem(withTitle: "Reload App View", action: #selector(reloadView), keyEquivalent: "r")
        viewMenu.addItem(NSMenuItem.separator())
        viewMenu.addItem(withTitle: "Toggle Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        viewMenuItem.submenu = viewMenu
        mainMenu.addItem(viewMenuItem)

        // 5. Emergency Menu
        let emMenuItem = NSMenuItem()
        let emMenu = NSMenu(title: "Emergency")
        emMenu.addItem(withTitle: "🚨 Open Overdose Protocol Modal", action: #selector(navEmergency), keyEquivalent: "E")
        emMenu.addItem(NSMenuItem.separator())
        emMenu.addItem(withTitle: "Call Never Use Alone (1-877-696-1996)", action: #selector(callNeverUseAlone), keyEquivalent: "")
        emMenu.addItem(withTitle: "Call SAMHSA Helpline (1-800-662-4357)", action: #selector(callSAMHSA), keyEquivalent: "")
        emMenuItem.submenu = emMenu
        mainMenu.addItem(emMenuItem)

        // 6. Window Menu
        let windowMenuItem = NSMenuItem()
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        windowMenuItem.submenu = windowMenu
        mainMenu.addItem(windowMenuItem)

        NSApp.mainMenu = mainMenu
    }

    // MARK: - Menu Actions

    @objc func showAbout() {
        let alert = NSAlert()
        alert.messageText = "Erowid SafeDB v2.0"
        alert.informativeText = "Evidence-based Harm Reduction, Clinical Drug Interaction Radar & Universal Erowid Archive.\n\nOffline-ready systematic database containing 561 psychoactive substances, multi-drug contraindication engine, dosage ladder brackets, and on-demand trip vault."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }

    @objc func reloadView() {
        webView.reload()
    }

    @objc func navDossiers() {
        webView.evaluateJavaScript("switchNav('dossiers');")
    }

    @objc func navRadar() {
        webView.evaluateJavaScript("switchNav('radar');")
    }

    @objc func navCatalog() {
        webView.evaluateJavaScript("switchNav('catalog');")
    }

    @objc func navVault() {
        webView.evaluateJavaScript("switchNav('vault');")
    }

    @objc func navReagents() {
        webView.evaluateJavaScript("switchNav('reagents');")
    }

    @objc func navHarvester() {
        webView.evaluateJavaScript("switchNav('harvester');")
    }

    @objc func navEmergency() {
        webView.evaluateJavaScript("openEmergencyModal();")
    }

    @objc func callNeverUseAlone() {
        if let url = URL(string: "tel:18776961996") {
            NSWorkspace.shared.open(url)
        }
    }

    @objc func callSAMHSA() {
        if let url = URL(string: "tel:18006624357") {
            NSWorkspace.shared.open(url)
        }
    }

    func showErrorAlert(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Erowid SafeDB Error"
        alert.informativeText = message
        alert.alertStyle = .critical
        alert.addButton(withTitle: "Quit")
        alert.runModal()
        NSApp.terminate(nil)
    }
}

// Bootstrap Cocoa Application
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()

