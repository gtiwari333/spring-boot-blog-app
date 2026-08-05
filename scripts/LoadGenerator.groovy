#!/usr/bin/env groovy

/**
 * Selenide-based load generator — mimics WebAppIT.java flow exactly.
 *
 * Requires: Groovy 5+, Java 21+, Chrome/Chromium installed
 * First run resolves @Grab dependencies automatically (~30s).
 *
 * Usage:
 *   groovy scripts/LoadGenerator.groovy
 *   groovy scripts/LoadGenerator.groovy --url http://localhost:8080 --duration 300 --users 3
 *   groovy scripts/LoadGenerator.groovy --headless false   # show browser window
 */

@Grab('com.codeborne:selenide:7.12.0')
@Grab('org.slf4j:slf4j-nop:2.0.17')

import com.codeborne.selenide.Selenide
import com.codeborne.selenide.SelenideElement
import com.codeborne.selenide.Condition
import com.codeborne.selenide.Configuration
import org.openqa.selenium.Keys

import java.time.Duration
import java.time.Instant
import java.util.concurrent.ThreadLocalRandom

// ---- CLI args ----
def cfg = [url: 'http://localhost:80', duration: 300, users: 3, headless: true, interval: 0.3]
def i = 0
while (i < args.length) {
    switch (args[i]) {
        case '--url':       cfg.url = args[++i]; break
        case '--duration':  cfg.duration = args[++i].toInteger(); break
        case '--users':     cfg.users = args[++i].toInteger(); break
        case '--headless':  cfg.headless = args[++i].toBoolean(); break
        case '--interval':  cfg.interval = args[++i].toDouble(); break
    }
    i++
}

final BASE            = cfg.url.toString().replaceAll('/$', '')
final DURATION_SECS   = cfg.duration
final USER_COUNT      = cfg.users
final INTERVAL        = cfg.interval
final PASSWORD        = 'pass'

Configuration.headless        = cfg.headless
Configuration.browser         = 'chrome'
Configuration.baseUrl         = BASE
Configuration.timeout         = 15000L
Configuration.pageLoadTimeout = 30000L
Configuration.screenshots     = false
Configuration.savePageSource  = false

def rng = ThreadLocalRandom.current()

println "╔══════════════════════════════════════════╗"
println "║  Blog Load Generator (Selenide/Groovy)   ║"
println "╠══════════════════════════════════════════╣"
println "║  URL:      ${BASE}"
println "║  Duration: ${DURATION_SECS}s"
println "║  Users:    ${USER_COUNT}"
println "║  Headless: ${Configuration.headless}"
println "║  Interval: ${INTERVAL}s"
println "╚══════════════════════════════════════════╝"


// ---- Page actions (matching WebAppIT selectors exactly) ----

def openPublicPage = {
    Selenide.open('/')
    Selenide.$('body').shouldBe(Condition.visible)
}

def login = { String username ->
    // Always start from homepage
    Selenide.open('/')
    Selenide.$('body').shouldBe(Condition.visible)
    sleep(100)

    // If logged in, log out first
    if (!Selenide.$('#login-link').exists() && Selenide.$('#navbarDropdownMenuLink').exists()) {
        Selenide.$('#navbarDropdownMenuLink').click()
        sleep(100)
        Selenide.$('#logout-link').shouldBe(Condition.visible).click()
        Selenide.$('#login-link').shouldBe(Condition.visible)
        sleep(150)
    }

    // Click login link from public page
    Selenide.$('#login-link').shouldBe(Condition.visible).click()

    // Fill and submit login form
    Selenide.$('body').shouldBe(Condition.visible)
    Selenide.$('#username').shouldBe(Condition.visible).setValue(username)
    Selenide.$('#password').shouldBe(Condition.visible).setValue(PASSWORD)
    Selenide.$('#password').sendKeys(Keys.ENTER)

    // Wait for post-login redirect
    Selenide.$('#navbarDropdownMenuLink').shouldBe(Condition.visible)
    sleep(200)
}

def postNote = { String title, String content ->
    // Go home first to ensure form is present
    Selenide.open('/')
    Selenide.$('body').shouldBe(Condition.visible)
    // LoggedInHomePage.postNote()
    Selenide.$('#title').shouldBe(Condition.visible)
    Selenide.$('#title').setValue(title)
    Selenide.$('#content').setValue(content)
    Selenide.$('#postNote-btn').pressEnter()
    Selenide.$('body').shouldBe(Condition.visible)
    sleep(200)
}

def openUserPage = {
    // Go home first to ensure navbar is present
    Selenide.open('/')
    Selenide.$('body').shouldBe(Condition.visible)
    // BaseLoggedInPage.openUserPage()
    Selenide.$('#user-note-link').shouldBe(Condition.visible).click()
    Selenide.$('body').shouldBe(Condition.visible)
    sleep(150)
}

def editNote = { int row, String title, String content ->
    // UserPage.editNote(row)
    Selenide.$x(".//table/tbody/tr[${row}]/td[5]/span/a").click()
    Selenide.$('body').shouldBe(Condition.visible)
    // NoteEditPage.updateNote()
    if (Selenide.$('#title').exists()) {
        Selenide.$('#title').setValue(title)
        Selenide.$('#content').setValue(content)
        Selenide.$('#updateNote-btn').pressEnter()
        Selenide.$('body').shouldBe(Condition.visible)
    }
    sleep(200)
}

def deleteNote = { int row ->
    // UserPage.deletePage(row)
    Selenide.$x(".//table/tbody/tr[${row}]/td[6]/span/a").click()
    Selenide.$('body').shouldBe(Condition.visible)
    sleep(200)
}

def logout = {
    // Ensure we're on a page with the navbar
    Selenide.open('/')
    Selenide.$('body').shouldBe(Condition.visible)
    // BaseLoggedInPage.logout()
    Selenide.$('#navbarDropdownMenuLink').shouldBe(Condition.visible).click()
    sleep(100)
    Selenide.$('#logout-link').shouldBe(Condition.visible).click()
    Selenide.$('#login-link').shouldBe(Condition.visible)  // confirms logged out
    sleep(200)
}

def signup = { String username ->
    Selenide.open('/signup')
    Selenide.$('body').shouldBe(Condition.visible)
    Selenide.$('#firstName').setValue('Load')
    Selenide.$('#lastName').setValue('Test')
    Selenide.$('#email').setValue("${username}@test.com")
    Selenide.$('#uniqueId').setValue(username)       // signup uses #uniqueId for username
    Selenide.$('#pwdPlaintext').setValue(PASSWORD)   // signup uses #pwdPlaintext for password
    Selenide.$('button[type="submit"], input[type="submit"]').click()
    Selenide.$('body').shouldBe(Condition.visible)
    sleep(300)
}

def browseAdmin = {
    Selenide.open('/admin')
    Selenide.$('body').shouldBe(Condition.visible)
    sleep(150)
}

// ---- Main Loop ----

def deadline = Instant.now().plusSeconds(DURATION_SECS)
def actionCount = 0
def noteCounters = new int[USER_COUNT + 1]
def editRowCounters = new int[USER_COUNT + 1]
def loggedInUser = null

enum Action {
    BROWSE_PUBLIC, BROWSE_USER, POST_NOTE, EDIT_NOTE,
    DELETE_NOTE, LOGOUT_RELOGIN, SIGNUP, BROWSE_ADMIN
}
def weights = [25, 20, 25, 10, 5, 8, 2, 5]

def pickWeighted = { ->
    int total = weights.sum()
    int roll = rng.nextInt(total)
    int cum = 0
    for (int j = 0; j < Action.values().size(); j++) {
        cum += weights[j]
        if (roll < cum) return Action.values()[j]
    }
    return Action.BROWSE_PUBLIC
}

try {
    while (Instant.now() < deadline) {
        def action = pickWeighted()
        def userIdx = rng.nextInt(1, USER_COUNT + 1)
        def username = "user${userIdx}"

        try {
            switch (action) {
                case Action.BROWSE_PUBLIC:
                    openPublicPage()
                    break

                case Action.BROWSE_USER:
                    if (loggedInUser == null) { login(username); loggedInUser = username }
                    openUserPage()
                    openPublicPage()
                    break

                case Action.POST_NOTE:
                    if (loggedInUser == null) { login(username); loggedInUser = username }
                    noteCounters[userIdx]++
                    editRowCounters[userIdx]++
                    def n = noteCounters[userIdx]
                    postNote("Load Note #${n}", "Generated at ${java.time.LocalTime.now().truncatedTo(java.time.temporal.ChronoUnit.SECONDS)}")
                    break

                case Action.EDIT_NOTE:
                    if (loggedInUser == null) { login(username); loggedInUser = username }
                    if (editRowCounters[userIdx] > 0) {
                        openUserPage()
                        def row = rng.nextInt(1, Math.min(editRowCounters[userIdx] + 1, 11))
                        editNote(row, "Edited #${row}", "Updated at ${java.time.LocalTime.now().truncatedTo(java.time.temporal.ChronoUnit.SECONDS)}")
                    }
                    break

                case Action.DELETE_NOTE:
                    if (loggedInUser == null) { login(username); loggedInUser = username }
                    if (editRowCounters[userIdx] > 0) {
                        openUserPage()
                        def row = rng.nextInt(1, Math.min(editRowCounters[userIdx] + 1, 11))
                        deleteNote(row)
                        editRowCounters[userIdx] = Math.max(0, editRowCounters[userIdx] - 1)
                    }
                    break

                case Action.LOGOUT_RELOGIN:
                    if (loggedInUser != null) { logout(); loggedInUser = null }
                    def newUser = rng.nextInt(1, USER_COUNT + 1)
                    login("user${newUser}")
                    loggedInUser = "user${newUser}"
                    break

                case Action.SIGNUP:
                    if (loggedInUser != null) { logout(); loggedInUser = null }
                    signup("lt${System.currentTimeMillis() % 100000}")
                    break

                case Action.BROWSE_ADMIN:
                    if (loggedInUser != 'system') { login('system'); loggedInUser = 'system' }
                    browseAdmin()
                    break
            }

            actionCount++
            if (actionCount % 25 == 0) {
                def remaining = Duration.between(Instant.now(), deadline).seconds
                println "  [${remaining}s left]  ${actionCount} actions  |  user: ${loggedInUser ?: 'none'}"
            }

        } catch (Exception e) {
            String msg = e.message ?: ''
            System.err.println "  [WARN] ${action}: ${msg.take(120)}"
            loggedInUser = null
            sleep(500)
            try { Selenide.open('/'); Selenide.$('body').shouldBe(Condition.visible) } catch (ignored) {}
        }

        sleep((long) (INTERVAL * 1000 * rng.nextDouble(0.4, 1.6)))
    }

} finally {
    Selenide.closeWebDriver()
}

println "\nDone. ${actionCount} actions in ${DURATION_SECS}s (${String.format('%.1f', actionCount / (double) DURATION_SECS)}/s)"
