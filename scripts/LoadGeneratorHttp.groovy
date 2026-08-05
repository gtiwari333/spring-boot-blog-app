#!/usr/bin/env groovy

/**
 * HTTP-level load generator — no browser, pure HTTP with session cookies.
 * Uses Java's built-in HttpClient. Zero @Grab, zero browser, minimal memory.
 *
 * Usage:
 *   groovy scripts/LoadGeneratorHttp.groovy
 *   groovy scripts/LoadGeneratorHttp.groovy --url http://localhost:8080 --duration 300 --users 10
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
def rng             = ThreadLocalRandom.current()
def CSRF_PATTERN    = Pattern.compile('name="_csrf"[^>]*value="([^"]+)"')
def sessions        = [:] as Map<String, HttpClient>
def noteCounters    = [:] as Map<String, Integer>

println "╔══════════════════════════════════════════╗"
println "║  Blog Load Generator (HTTP/Groovy)       ║"
println "╠══════════════════════════════════════════╣"
println "║  URL:      ${BASE}"
println "║  Duration: ${DURATION_SECS}s"
println "║  Users:    ${USER_COUNT}"
println "║  Interval: ${INTERVAL}s"
println "╚══════════════════════════════════════════╝"

// ---- All actions as CLOSURES (not methods) to capture script scope ----

def extractCsrf = { String html ->
    def m = CSRF_PATTERN.matcher(html)
    m.find() ? m.group(1) : null
}

def getSession = { String username ->
    if (!sessions.containsKey(username)) {
        def cm = new CookieManager()
        cm.setCookiePolicy(CookiePolicy.ACCEPT_ALL)
        sessions[username] = HttpClient.newBuilder()
            .cookieHandler(cm)
            .followRedirects(HttpClient.Redirect.NORMAL)
            .connectTimeout(Duration.ofSeconds(5))
            .build()
        noteCounters[username] = 0
    }
    sessions[username]
}

def httpGet = { String username, String path ->
    def client = getSession(username)
    def req = HttpRequest.newBuilder()
        .uri(URI.create(BASE + path))
        .timeout(Duration.ofSeconds(10))
        .GET()
        .build()
    client.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8))
}

def httpPost = { String username, String path, Map<String, String> fields ->
    def client = getSession(username)
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

def login = { String username ->
    def resp = httpGet(username, '/login')
    def csrf = extractCsrf(resp.body())
    def fields = [username: username, password: PASSWORD]
    if (csrf) fields._csrf = csrf
    def loginResp = httpPost(username, '/auth/login', fields)
    loginResp.body().toLowerCase().contains('logout')
}

def browsePublic = { String username -> httpGet(username, '/') }

def browseUserNotes = { String username ->
    httpGet(username, '/')
    httpGet(username, '/note')
}

def postNote = { String username ->
    def c = (noteCounters[username] ?: 0) + 1
    noteCounters[username] = c
    def resp = httpGet(username, '/')
    def csrf = extractCsrf(resp.body())
    def fields = [title: "Load Note #${c}", content: "Generated at ${LocalTime.now().truncatedTo(ChronoUnit.SECONDS)}"]
    if (csrf) fields._csrf = csrf
    httpPost(username, '/note/add', fields)
    c
}

def editNote = { String username ->
    def c = noteCounters[username] ?: 0
    if (c <= 0) return
    def noteId = rng.nextInt(1, c * 2 + 1)
    def resp = httpGet(username, "/note/edit/${noteId}")
    def csrf = extractCsrf(resp.body())
    def fields = [id: noteId.toString(), title: "Edited #${noteId}", content: "Updated at ${LocalTime.now().truncatedTo(ChronoUnit.SECONDS)}"]
    if (csrf) fields._csrf = csrf
    httpPost(username, '/note/edit', fields)
}

def deleteNote = { String username ->
    def c = noteCounters[username] ?: 0
    if (c <= 3) return
    def noteId = rng.nextInt(1, c + 1)
    httpGet(username, "/note/delete/${noteId}")
    noteCounters[username] = Math.max(0, c - 1)
}

def doSignup = { String username ->
    def resp = httpGet(username, '/signup')
    def csrf = extractCsrf(resp.body())
    def fields = [firstName: 'Load', lastName: 'Test', email: "${username}@test.com",
                  uniqueId: username, pwdPlaintext: PASSWORD]
    if (csrf) fields._csrf = csrf
    httpPost(username, '/signup', fields)
}

def browseAdmin = { String username -> httpGet(username, '/admin') }

def logoutUser = { String username ->
    // Spring Security requires POST for logout
    def resp = httpGet(username, '/')
    def csrf = extractCsrf(resp.body())
    httpPost(username, '/auth/logout', csrf ? [_csrf: csrf] : [:])
    sessions.remove(username)
    noteCounters.remove(username)
}

// ---- Main Loop ----

def deadline = Instant.now().plusSeconds(DURATION_SECS)
def actionCount = 0
def loggedInUsers = [] as Set

enum Action {
    BROWSE_PUBLIC, BROWSE_USER, POST_NOTE, EDIT_NOTE,
    DELETE_NOTE, LOGOUT_RELOGIN, SIGNUP, BROWSE_ADMIN
}
def weights = [25, 20, 25, 10, 5, 8, 0, 5]  // SIGNUP disabled (app bug on validation failure)

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

try {
    while (Instant.now() < deadline) {
        def action = pickWeighted()
        def userIdx = rng.nextInt(1, USER_COUNT + 1) % SEEDED_USERS + 1
        def username = "user${userIdx}"

        try {
            switch (action) {
                case Action.BROWSE_PUBLIC:
                    browsePublic(username)
                    break
                case Action.BROWSE_USER:
                    if (!loggedInUsers.contains(username)) {
                        if (login(username)) loggedInUsers.add(username)
                    }
                    if (loggedInUsers.contains(username)) browseUserNotes(username)
                    break
                case Action.POST_NOTE:
                    if (!loggedInUsers.contains(username)) {
                        if (login(username)) loggedInUsers.add(username)
                    }
                    if (loggedInUsers.contains(username)) postNote(username)
                    break
                case Action.EDIT_NOTE:
                    if (!loggedInUsers.contains(username)) {
                        if (login(username)) loggedInUsers.add(username)
                    }
                    if (loggedInUsers.contains(username)) editNote(username)
                    break
                case Action.DELETE_NOTE:
                    if (!loggedInUsers.contains(username)) {
                        if (login(username)) loggedInUsers.add(username)
                    }
                    if (loggedInUsers.contains(username)) deleteNote(username)
                    break
                case Action.LOGOUT_RELOGIN:
                    logoutUser(username)
                    loggedInUsers.remove(username)
                    def newIdx = rng.nextInt(1, USER_COUNT + 1) % SEEDED_USERS + 1
                    if (login("user${newIdx}")) loggedInUsers.add("user${newIdx}")
                    break
                case Action.SIGNUP:
                    doSignup("lt${System.currentTimeMillis() % 100000}")
                    break
                case Action.BROWSE_ADMIN:
                    logoutUser(username)
                    loggedInUsers.remove(username)
                    if (login('system')) {
                        loggedInUsers.add('system')
                        browseAdmin('system')
                    }
                    break
            }

            actionCount++
            if (actionCount % 100 == 0) {
                def elapsed = Duration.between(deadline.minusSeconds(DURATION_SECS), Instant.now()).seconds
                if (elapsed > 0) {
                    def rate = actionCount / elapsed
                    println "  [${Duration.between(Instant.now(), deadline).seconds}s left]  ${actionCount} actions  |  ${loggedInUsers.size()} logged in  |  ~${String.format('%.0f', rate)}/s"
                }
            }

        } catch (Exception e) {
            System.err.println "  [WARN] ${action}: ${e.message?.take(120)}"
        }

        sleep((long) (INTERVAL * 1000 * rng.nextDouble(0.5, 1.5)))
    }

} finally {
    println "\nDone. ${actionCount} actions in ${DURATION_SECS}s (${String.format('%.1f', actionCount / (double) Math.max(1, DURATION_SECS))}/s)"
}
