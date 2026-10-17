#!/usr/bin/env groovy

/**
 * HTTP-level load generator — no browser, pure HTTP with session cookies.
 * Uses Java's built-in HttpClient. Zero @Grab, zero browser, minimal memory.
 *
 * One worker thread per --users; each worker drives its own session(s)
 * independently, so --users 50 = 50 concurrent clients.
 *
 * Usage:
 *   groovy scripts/LoadGeneratorHttp.groovy
 *   groovy scripts/LoadGeneratorHttp.groovy --url http://localhost:8082 --duration 300 --users 50
 *   groovy scripts/LoadGeneratorHttp.groovy --duration 60 --users 5 --interval 0.01
 */

import java.net.URI
import java.net.CookieManager
import java.net.CookiePolicy
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.time.Duration
import java.time.Instant
import java.time.LocalTime
import java.time.temporal.ChronoUnit
import java.util.concurrent.ThreadLocalRandom
import java.util.concurrent.atomic.AtomicInteger
import java.util.regex.Pattern

// ---- CLI args ----
def cfg = [url: 'http://localhost:80', duration: 300, users: 3, interval: 0.05]
def i = 0
while (i < args.length) {
    switch (args[i]) {
        case '--url':       cfg.url = args[++i]; break
        case '--duration':  cfg.duration = args[++i].toInteger(); break
        case '--users':     cfg.users = args[++i].toInteger(); break
        case '--interval':  cfg.interval = args[++i].toDouble(); break
    }
    i++
}

// All config as closure-captured locals (closures see these, methods don't)
def BASE            = cfg.url.toString().replaceAll('/$', '')
def DURATION_SECS   = cfg.duration
def USER_COUNT      = cfg.users
def INTERVAL        = cfg.interval
def PASSWORD        = 'pass'
def SEEDED_USERS    = 50
def CSRF_PATTERN    = Pattern.compile('name="_csrf"[^>]*value="([^"]+)"')

println "╔══════════════════════════════════════════╗"
println "║  Blog Load Generator (HTTP/Groovy)       ║"
println "╠══════════════════════════════════════════╣"
println "║  URL:      ${BASE}"
println "║  Duration: ${DURATION_SECS}s"
println "║  Users:    ${USER_COUNT} (one worker thread each)"
println "║  Interval: ${INTERVAL}s per worker"
println "╚══════════════════════════════════════════╝"

enum Action {
    BROWSE_PUBLIC, BROWSE_USER, POST_NOTE, EDIT_NOTE,
    DELETE_NOTE, LOGOUT_RELOGIN, SIGNUP, BROWSE_ADMIN
}
def weights = [25, 20, 25, 10, 5, 8, 0, 5]  // SIGNUP disabled (app bug on validation failure)

// ---- Per-worker factory: closures capture this worker's own state ----

def makeWorker = { String username ->
    def sessions   = [:] as Map<String, HttpClient>
    def loggedIn   = [] as Set<String>
    def noteCounter = 0
    def rng = ThreadLocalRandom.current()   // called inside the worker thread, so it's that thread's instance

    def extractCsrf = { String html ->
        def m = CSRF_PATTERN.matcher(html)
        m.find() ? m.group(1) : null
    }

    def getSession = { String uname ->
        if (!sessions.containsKey(uname)) {
            def cm = new CookieManager()
            cm.setCookiePolicy(CookiePolicy.ACCEPT_ALL)
            sessions[uname] = HttpClient.newBuilder()
                .cookieHandler(cm)
                .followRedirects(HttpClient.Redirect.NORMAL)
                .connectTimeout(Duration.ofSeconds(5))
                .build()
        }
        sessions[uname]
    }

    def httpGet = { String uname, String path ->
        def client = getSession(uname)
        def req = HttpRequest.newBuilder()
            .uri(URI.create(BASE + path))
            .timeout(Duration.ofSeconds(10))
            .GET()
            .build()
        client.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8))
    }

    def httpPost = { String uname, String path, Map<String, String> fields ->
        def client = getSession(uname)
        def body = fields.collect { k, v ->
            "${URLEncoder.encode(k, 'UTF-8')}=${URLEncoder.encode(v, 'UTF-8')}"
        }.join('&')
        def req = HttpRequest.newBuilder()
            .uri(URI.create(BASE + path))
            .timeout(Duration.ofSeconds(10))
            .header('Content-Type', 'application/x-www-form-urlencoded')
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build()
        client.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8))
    }

    def login = { String uname ->
        def resp = httpGet(uname, '/login')
        def csrf = extractCsrf(resp.body())
        def fields = [username: uname, password: PASSWORD]
        if (csrf) fields._csrf = csrf
        def loginResp = httpPost(uname, '/auth/login', fields)
        loginResp.body().toLowerCase().contains('logout')
    }

    def browsePublic = { httpGet(username, '/') }

    def browseUserNotes = {
        httpGet(username, '/')
        httpGet(username, '/note')
    }

    def postNote = {
        def c = noteCounter + 1
        noteCounter = c
        def resp = httpGet(username, '/')
        def csrf = extractCsrf(resp.body())
        def fields = [title: "Load Note #${c}", content: "Generated at ${LocalTime.now().truncatedTo(ChronoUnit.SECONDS)}"]
        if (csrf) fields._csrf = csrf
        httpPost(username, '/note/add', fields)
        c
    }

    def editNote = {
        def c = noteCounter
        if (c <= 0) return
        def noteId = rng.nextInt(1, c * 2 + 1)
        def resp = httpGet(username, "/note/edit/${noteId}")
        def csrf = extractCsrf(resp.body())
        def fields = [id: noteId.toString(), title: "Edited #${noteId}", content: "Updated at ${LocalTime.now().truncatedTo(ChronoUnit.SECONDS)}"]
        if (csrf) fields._csrf = csrf
        httpPost(username, '/note/edit', fields)
    }

    def deleteNote = {
        def c = noteCounter
        if (c <= 3) return
        def noteId = rng.nextInt(1, c + 1)
        httpGet(username, "/note/delete/${noteId}")
        noteCounter = Math.max(0, c - 1)
    }

    def doSignup = {
        def resp = httpGet(username, '/signup')
        def csrf = extractCsrf(resp.body())
        def fields = [firstName: 'Load', lastName: 'Test', email: "${username}@test.com",
                      uniqueId: username, pwdPlaintext: PASSWORD]
        if (csrf) fields._csrf = csrf
        httpPost(username, '/signup', fields)
    }

    def browseAdmin = {
        // Spring Security requires POST for logout
        def resp = httpGet(username, '/')
        def csrf = extractCsrf(resp.body())
        httpPost(username, '/auth/logout', csrf ? [_csrf: csrf] : [:])
        sessions.remove(username)
        loggedIn.remove(username)
        if (login('system')) {
            loggedIn.add('system')
            httpGet('system', '/admin')
        }
    }

    def pickWeighted = { ->
        int total = weights.sum()
        int roll = rng.nextInt(total)
        int cum = 0
        for (int j = 0; j < Action.values().size(); j++) {
            cum += weights[j]
            if (roll < cum) return Action.values()[j]
        }
        Action.BROWSE_PUBLIC
    }

    // Runs one weighted action; returns the closure the worker loop invokes
    return { ->
        switch (pickWeighted()) {
            case Action.BROWSE_PUBLIC:
                browsePublic()
                break
            case Action.BROWSE_USER:
                if (!loggedIn.contains(username)) {
                    if (login(username)) loggedIn.add(username)
                }
                if (loggedIn.contains(username)) browseUserNotes()
                break
            case Action.POST_NOTE:
                if (!loggedIn.contains(username)) {
                    if (login(username)) loggedIn.add(username)
                }
                if (loggedIn.contains(username)) postNote()
                break
            case Action.EDIT_NOTE:
                if (!loggedIn.contains(username)) {
                    if (login(username)) loggedIn.add(username)
                }
                if (loggedIn.contains(username)) editNote()
                break
            case Action.DELETE_NOTE:
                if (!loggedIn.contains(username)) {
                    if (login(username)) loggedIn.add(username)
                }
                if (loggedIn.contains(username)) deleteNote()
                break
            case Action.LOGOUT_RELOGIN:
                // POST logout, then log back in
                def resp = httpGet(username, '/')
                def csrf = extractCsrf(resp.body())
                httpPost(username, '/auth/logout', csrf ? [_csrf: csrf] : [:])
                sessions.remove(username)
                loggedIn.remove(username)
                if (login(username)) loggedIn.add(username)
                break
            case Action.SIGNUP:
                doSignup()
                break
            case Action.BROWSE_ADMIN:
                browseAdmin()
                break
        }
    }
}

// ---- Main Loop: one worker thread per user, all running until the deadline ----

def deadline   = Instant.now().plusSeconds(DURATION_SECS)
def startTime  = Instant.now()
def actionCount = new AtomicInteger()
def errorCount  = new AtomicInteger()

// user1..user50 are seeded; if --users exceeds that, wrap around (each worker
// still gets its own session, so two workers may share a username)
def usernames = (1..USER_COUNT).collect { "user${(it - 1) % SEEDED_USERS + 1}" }

def workers = usernames.collect { uname ->
    Thread.start {
        def runAction = makeWorker(uname)
        while (Instant.now() < deadline) {
            try {
                runAction()
                actionCount.incrementAndGet()
            } catch (Exception e) {
                errorCount.incrementAndGet()
                System.err.println "  [WARN] ${uname}: ${e.message?.take(120)}"
            }
            sleep((long) (INTERVAL * 1000 * ThreadLocalRandom.current().nextDouble(0.5, 1.5)))
        }
    }
}

def progress = Thread.start {
    while (true) {
        sleep(2000)
        if (!Instant.now().isBefore(deadline)) break
        def elapsed = Math.max(1, Duration.between(startTime, Instant.now()).seconds)
        def rate = actionCount.get() / (double) elapsed
        println "  [${Duration.between(Instant.now(), deadline).seconds}s left]  ${actionCount.get()} actions  |  ${errorCount.get()} errors  |  ~${String.format('%.0f', rate)}/s"
    }
}

try {
    workers.each { it.join() }
} finally {
    progress.join()
    def elapsed = Math.max(1, Duration.between(startTime, Instant.now()).seconds)
    println "\nDone. ${actionCount.get()} actions in ${elapsed}s (${String.format('%.1f', actionCount.get() / (double) elapsed)}/s)"
}
