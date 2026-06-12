

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## SECTION I
## THE OFFENSIVE LANDSCAPE
How Automated Evasion Systems Work — A Five-Layer Technical Analysis
Chapter 1 — The Five-Layer Arms Race Framework
Modern bot detection is not a single system — it is a stack of simultaneous, parallel checks.
Understanding the field requires appreciating this multi-dimensional structure. Commercial bot
detection platforms such as Cloudflare Bot Management, DataDome, Akamai Bot Manager,
PerimeterX, and Imperva do not rely on any single signal. They collect evidence from five
distinct technical layers at the same time and compute a composite risk score. A tool that
evades Layer 2 flawlessly can still be blocked because Layer 3 gave it away.
This is the fundamental reason the field is described as an arms race. Every improvement in
detection forces a corresponding improvement in evasion tools, and vice versa. It is also why
tools that worked in 2021 may be entirely detected by 2024 systems. The five layers, ordered
from the outer network edge inward to user interaction, are:
LayerNameWhat Is InspectedExample Detection Signal
Layer 1Core
## Automation
## Framework
Protocol fingerprint, automation
binaries
CDP (Chrome DevTools Protocol)
connection signature
Layer 2Stealth / Anti-
## Detection
JS environment integrity,
navigator properties
navigator.webdriver = true; Selenium
global variables in window
Layer 3TLS / Network
## Fingerprint
TLS ClientHello structure,
HTTP/2 settings
JA3/JA4 hash mismatch between
User-Agent and actual TLS
Layer 4Browser / DOM
## Fingerprint
Canvas, WebGL,
AudioContext, hardware
signals
Identical canvas hash across many
IPs; impossible hardware combination
Layer 5Behavioral
## Biometrics
Mouse, keyboard, scroll
interaction patterns
Perfectly straight mouse trajectory;
zero hesitation before click
## 1.1  The Detection Stack — Conceptual Diagram
The diagram below shows how bot detection operates. All five layers are evaluated in parallel.
A single failure anywhere in the stack is sufficient to trigger blocking or a CAPTCHA challenge.
## ┌──────────────────────────────────────────────────────────────────────────┐
│             BOT DETECTION SYSTEM (Cloudflare / DataDome / Akamai)       │
│   ALL signals collected in parallel — ONE failure = blocked / challenged │
## └─────────────────────────────────┬────────────────────────────────────────┘

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
│ parallel signal collection
## ┌────────────────────────────┼──────────────────────────────┐
## │                            │                              │
## ┌────▼────────┐        ┌──────────▼──────────┐        ┌─────────▼──────────┐
## │  LAYER 3    │        │     LAYER 4          │        │    LAYER 5         │
│  TLS/Network│        │  Browser / DOM       │        │  Behavioral        │
## │  Fingerprint│        │  Fingerprint         │        │  Biometrics        │
│  JA3 / JA4  │        │  Canvas, WebGL,      │        │  Mouse, Keyboard,  │
│  HTTP/2     │        │  AudioContext,        │        │  Scroll — timing,  │
│  SETTINGS   │        │  Hardware signals     │        │  velocity, curve   │
## └─────────────┘        └─────────────────────┘        └────────────────────┘
## │                            │                              │
## └────────────────────────────┼──────────────────────────────┘
## │
## ┌────────────▼──────────────┐
## │         LAYER 2           │
## │  Stealth / Patch Level    │
│  JS shims vs C++ binary   │
│  patch (navigator, CDP)   │
## └────────────┬──────────────┘
## │
## ┌────────────▼──────────────┐
## │         LAYER 1           │
## │  Core Automation          │
## │  Selenium / Playwright /  │
│  Puppeteer / nodriver /   │
│  httpx / curl-cffi        │
## └───────────────────────────┘
## 1.2  Why Every Layer Must Be Addressed
Consider a concrete example. A developer uses Camoufox (a binary-patched Firefox that
defeats Layer 2 and Layer 4) but routes traffic through a datacenter IP instead of a residential
proxy. The network layer (Layer 3) reveals the IP belongs to a cloud provider ASN. Cloudflare
does not care that the browser was perfectly stealthy. The IP is blocked immediately.
Conversely, consider a perfect residential IP and perfect TLS fingerprint (Layers 3 and 4 fine),
but the automation uses Selenium with default ChromeDriver. The very first HTTP request
reveals navigator.webdriver === true via JavaScript execution. Blocked instantly at Layer 2.
This layered reality is why the arms race generates so many specialized tools. Each tool
addresses a specific layer, and combining them correctly is the core engineering challenge.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## Chapter 2 — Layer 1: Core Browser Automation
## Frameworks
The foundational layer consists of the framework that drives the browser or makes HTTP
requests. Every other layer is built on top of this foundation. The choice of core framework has
profound implications for detection risk, performance, scalability, and maintainability.
## 2.1  Two Fundamental Architectures
There   are   two   fundamentally   different   approaches   to   automating   web   interactions.
Understanding the difference is essential because bot detectors treat them very differently:
•Browser Automation (CDP/WebDriver): A real browser process is launched, and the
automation framework sends commands to it over a protocol — either WebDriver
(W3C standard, used by Selenium) or Chrome DevTools Protocol (CDP, used by
Playwright and Puppeteer). The browser renders JavaScript, executes event loops,
and produces a full browsing environment. This approach is necessary when the
target site uses JavaScript-rendered content or performs client-side behavioral
analysis. The cost is high CPU/memory consumption and a detectable protocol
signature.
•HTTP-only Automation (no browser): Libraries like httpx, curl-cffi, requests, or Scrapy
make direct HTTP requests without launching a browser. No JavaScript is executed.
This is 10-50x faster and requires far less memory. It is undetectable as browser
automation by Layer 4 signals because no browser fingerprint is generated. The
limitation: it cannot handle JavaScript-rendered content or complete browser-based
CAPTCHAs.
## 2.2  Framework Reference Table
LibraryLanguageProtocolGitHu
b
## Stars
## Categ
ory
## Key Notes
SeleniumPython/
Java/JS/
## C#
WebDriver
## (W3C)
~31kBrows
er
Oldest (2004). All browsers. CDP-
detectable by default
PlaywrightPython/
## JS/.NET/
## Java
## CDP +
WebSocket
~67kBrows
er
Microsoft. Fast, modern. Native network
interception
PuppeteerJavaScript/
## Node.js
CDP~88kBrows
er
Google's own. Chrome & Firefox. Large
ecosystem
PyppeteerPythonCDP~7kBrows
er
Python port of Puppeteer. Lags
upstream in updates
DrissionPa
ge
PythonCDP hybrid~12kBrows
er
Chinese origin. Hybrid HTTP+browser
mode
nodriverPythonMinimal
## CDP
~8kBrows
er
Wins bypass benchmarks by avoiding
full CDP signature
CypressJavaScriptIn-browser
## JS
~48kTestin
g
E2E testing focus. Not designed for
scraping at scale
ScrapyPythonHTTP only~52kHTTPSpider framework. Fast. No JS

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
LibraryLanguageProtocolGitHu
b
## Stars
## Categ
ory
## Key Notes
execution capability
curl-cffiPythonHTTP/TLS~13kHTTPTLS impersonation built-in. Fastest for
non-JS targets
httpxPythonHTTP/1+2
async
~13kHTTPAsync HTTP. No JS. Pair with TLS
tools for stealth
MechanizePythonHTTP~2kHTTPOld-school. Browser-like HTTP
navigation. No JS
2.3  The CDP Detection Problem
Chrome DevTools Protocol is a powerful debugging interface built into Chromium. Playwright
and Puppeteer use CDP to control the browser. The problem: CDP introduces unique
detectable   signals.   When   CDP   is   active,   the   browser   disables   certain   background
optimizations and enables debugging ports. Sophisticated bot detection identifies these
signals in several ways:
•The Runtime.enable CDP command changes how V8 (the JavaScript engine) reports
execution context information — detectable via the
window.cdc_adoQpoasnfa76pfcZLmcfl_Array property injected by ChromeDriver.
•CDP opens a WebSocket connection on a specific debugging port, visible to network
analysis.
•Headless Chrome exposes document.hidden = true differently from headed Chrome,
as certain browser animations are suppressed.
•The stack trace of Error objects in headless mode contains different internal frame
references than headed mode.
nodriver specifically addresses this by avoiding the Runtime.enable command and minimizing
CDP usage to the bare minimum needed for control. This significantly reduces the protocol-
level detection surface, which is why benchmark studies show nodriver achieving a 0%
blocking rate on protocol-fingerprinting targets where Playwright forks fail.
2.4  Choosing the Right Framework
## Decision Rule
If the target has accessible API endpoints, server-rendered HTML, or easily reverse-
engineered network calls: use curl-cffi or httpx. It will be 10-50x faster, use far fewer resources,
and have a smaller detection surface. Only use browser automation (Playwright, Puppeteer,
nodriver) when JavaScript rendering, CAPTCHA solving, or complex browser interaction is
genuinely required. The most common mistake is using a full browser when HTTP-only
automation would suffice.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 3 — Layer 2: Stealth and Anti-Detection
## Patching
When a standard browser is launched via automation, it exposes a multitude of signals that
identify it as non-human-controlled. Layer 2 tools attempt to suppress these signals. There are
two fundamentally different architectural approaches, with dramatically different effectiveness.
3.1  Architecture A: JavaScript-Shim Level (Weaker)
JavaScript-shim tools work by injecting JavaScript into every page before it executes. These
scripts overwrite or "patch" browser properties that reveal automation:
•navigator.webdriver — Set to undefined (default value when controlled by automation
is true)
•chrome.runtime — Recreated to appear non-empty
•navigator.plugins — Populated with fake plugin entries (empty in headless)
•window.chrome — Added to appear as a real Chrome environment
•Permissions API — Overridden to return realistic permission states
•WebGL renderer — Overridden to not return "SwiftShader" (the headless GPU)
The limitation is fundamental: modern detection systems do not just check these surface
properties. They examine the prototype chain, look for inconsistencies in the JS engine's
internal state, check whether patched functions behave identically to native ones, and look for
"lie detection" signals — cases where the claimed value and the measurable behavior don't
match. A patched navigator.webdriver of undefined combined with a SwiftShader WebGL
renderer is internally inconsistent in a way that CreepJS and similar tools detect immediately.
3.2  Architecture B: Binary-Patch Level (Stronger)
Binary-patch tools modify the browser source code or compiled binary before launch. The
headless detection signals are removed at the C++ level, not masked at the JavaScript level.
This means the browser genuinely does not have those properties — it cannot be "caught
lying" because it is not lying. The actual C++ code that sets navigator.webdriver = true is
patched to not set it.
Why Binary-Level Patching Is Harder to Detect
JavaScript-shim tools intercept property access at the ECMAScript layer. Advanced detectors
can bypass these shims by accessing the underlying V8 bytecode, checking prototype chain
integrity, or exploiting the fact that native functions have different internal representations than
overwritten ones (Function.prototype.toString() behaves differently for native vs. patched
functions). Binary-level patches cannot be detected through JavaScript introspection because
the underlying C++ runtime genuinely has the property removed.
## 3.3  Stealth Tool Reference
ToolApproachGitHub Stars
## (2026)
## Base
## Browse
r
## Headless
## Detection
## Rate
## Maintenance
## Status
puppeteer-extra-
plugin-stealth
JS shim (~20
patches)
~15kChromiu
m
## High (outdated
patches)
Stale — last
major update

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
ToolApproachGitHub Stars
## (2026)
## Base
## Browse
r
## Headless
## Detection
## Rate
## Maintenance
## Status
## 2023
playwright-stealthJS shim (port
of above)
~8kChromiu
m
## High (same
generation)
## Limited
maintenance
undetected-
chromedriver (UC)
ChromeDriver
binary patch
~41kChromeModerateActive
community
SeleniumBase UC
## Mode
CDP Mode +
UC patches
~13kChrome/
## Firefox
Moderate-LowActively
maintained
PatchrightPlaywright
internal patch
~3.2kChromiu
m
## ~67%
(CreepJS
benchmark)
Very active
## (2026)
CamoufoxFirefox C++
source fork
~8.4kFirefox~0%
## (benchmark
leader)
Active — best
OSS score
CloakBrowserChromium C+
+ source patch
Trending 2026Chromiu
m
Very low
(binary level)
## New —
launched early
## 2026
3.4  How Camoufox Works — The C++ Approach in Detail
Camoufox forks the Firefox source code and applies stealth patches at the C++ compilation
level. Understanding what this means technically:
1.The Firefox source tree (written in C++) contains the code that sets
navigator.webdriver, exposes headless-only APIs, and implements behavior
differences between headed and headless mode.
2.Camoufox modifies these source files — changing C++ function implementations —
then recompiles the entire Firefox binary from scratch.
3.Every fingerprinting signal that anti-bot systems look for (canvas rendering, WebGL
renderer string, AudioContext behavior, font metrics, network timing, memory API
responses) is controlled at the binary level.
4.When a detection script queries these properties, it receives the values a real Firefox
installation would provide — because the underlying code is real Firefox code with
targeted modifications.
5.This means Function.prototype.toString() checks, prototype chain analysis, and
V8/SpiderMonkey bytecode examination all show genuine native behavior.
Camoufox achieves 0% headless detection rate on standard benchmark tests, making it the
strongest open-source stealth browser available as of 2026.
## 3.5  The 2026 Benchmark
ToolProtocol
## Fingerprint
## Targets
## Behavioral
## Targets
Overall ScoreNotes
nodriver0% blockedLowBest on protocolAvoids CDP signature
entirely

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
ToolProtocol
## Fingerprint
## Targets
## Behavioral
## Targets
Overall ScoreNotes
CamoufoxLow0% headless
detected
Best OSS stealthC++ binary patches —
## Firefox
CloakBrowserLowVery lowStrong new entryChromium C++
patches — 2026
PatchrightModerate~33% pass rateGood Playwright
drop-in
67% stealth on
CreepJS
SeleniumBase
## UC
ModerateModerateAcceptable for
many sites
Actively maintained
puppeteer-
stealth
HighHighLargely obsolete
vs modern
Patches written for
Chrome 109 era

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 4 — Layer 3: TLS and Network-Level
## Fingerprinting
This layer is the most commonly missed by people learning web automation, yet it is one of the
first things that commercial bot detection systems check. The detection happens before any
HTTP data is exchanged — at the TLS handshake, in the first milliseconds of a connection.
4.1  The TLS Handshake and What It Reveals
Every HTTPS connection begins with a TLS handshake. Before any HTTP headers or page
content are transmitted, the client sends a ClientHello message that contains a detailed
description of its capabilities:
•TLS version supported (1.2, 1.3, etc.)
•Cipher suites — a list of encryption algorithms the client supports, in preference order
•TLS extensions — additional parameters like server name indication, supported
groups, ALPN protocols
•Elliptic curve groups — for ECDH key exchange
•EC point formats — how elliptic curve points should be encoded
This combination of parameters is characteristic of the TLS library used by the client. Chrome,
Firefox, curl, Python's ssl module, and Node.js all produce different ClientHello structures
because   they   use   different   underlying   TLS   implementations   with   different   default
configurations.
4.2  JA3 and JA4 — The Fingerprinting Methods
JA3 is a technique developed by Salesforce Engineering that creates a fingerprint from the
TLS ClientHello. It concatenates the TLS version, cipher suites, extensions, elliptic curves, and
EC point formats into a string and produces an MD5 hash. The result is a short hash that
identifies the TLS library in use with high accuracy.
MethodWhat It HashesDetection CapabilityPractical Use
JA3TLS version + cipher
suites + extensions +
curves + EC formats
Identifies TLS library
(Python vs Chrome vs
## Firefox)
Widely deployed; part of
Cloudflare, Akamai baseline
JA4Extended JA3 + ALPN
order + extension order +
more dimensions
More robust
fingerprint; harder to
spoof; includes JA4S
for servers
2024+ deployments; more
dimensions than JA3 alone
JA4HHTTP/1.1 header
fingerprint
Captures header
order, cookie
presence, language
settings
Supplements TLS fingerprint
with HTTP layer analysis
JA4XX.509 certificate analysisServer-side certificate
fingerprinting
Used by Akamai and others for
mutual inspection
## HTTP/2
## SETTINGS
## HTTP/2 SETTINGS
frame parameters
Window size, header
table size, stream
priorities
Chrome, Firefox, curl have
distinct HTTP/2 configurations

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## 4.3  The Detection Mismatch Problem
The attack surface for TLS detection is the mismatch between the claimed User-Agent and the
actual TLS fingerprint. A request claiming to be Chrome 124 on Windows but using Python's
urllib3 TLS fingerprint is immediately inconsistent:
User-Agent: "Mozilla/5.0 ... Chrome/124.0 ..."
TLS JA3:     a0e9f5d64349fb13191bc781f81f42e1  ← Python/urllib3 fingerprint
## Expected:
TLS JA3:     73362...  ← Actual Chrome 124 on Windows fingerprint
Result: MISMATCH DETECTED → Request blocked or scored as bot
This mismatch is detectable in the very first milliseconds, before any JavaScript runs, before
any CAPTCHA appears, before any behavioral analysis is possible. This is why TLS
impersonation is an essential component of any serious automation setup.
4.4  Libraries for TLS Fingerprint Impersonation
LibraryLangu
age
## JA3/JA4
## Support
GitHu
b
## Stars
## Key Notes
curl-cffiPythonFull — browser-
specific presets
~13kFastest Python HTTP + TLS
impersonation. Industry standard 2024-
## 2026
curl-impersonateC (curl
fork)
Full — compiles
per browser
~16kBase library. Patches curl to match
Chrome/Firefox TLS exactly
tls-client (Go)GoFull~4kHigh-performance Go HTTP with TLS
impersonation. For Go scrapers
tls-requestsPythonPartial~200Lightweight alternative. Updated Jan
## 2026
reqwest + custom
## TLS
RustCustomN/ARust HTTP with full TLS configuration
for custom fingerprints
4.5  HTTP/2 Fingerprinting
Beyond TLS, HTTP/2 introduces additional fingerprinting dimensions. Chrome, Firefox, and
curl all send different HTTP/2 SETTINGS frames at the start of a connection. The SETTINGS
frame specifies values like:
•HEADER_TABLE_SIZE — the initial size of the HPACK compression table
•ENABLE_PUSH — whether server push is accepted
•INITIAL_WINDOW_SIZE — the initial flow control window
•MAX_FRAME_SIZE — maximum frame payload size
•MAX_HEADER_LIST_SIZE — maximum header list size
Chrome sends specific values for all these parameters, in a specific order. Firefox sends
different values. A Python httpx client sends yet another combination. Akamai Bot Manager
specifically analyzes HTTP/2 SETTINGS frames as part of its enhanced TLS fingerprinting,
making this a distinct detection dimension even when JA3/JA4 is perfectly impersonated.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 5 — Layer 4: Browser and DOM Fingerprinting
Browser fingerprinting is the richest academic research area in this field. Unlike TLS
fingerprinting, which operates at the network layer, browser fingerprinting operates inside the
rendered page using JavaScript APIs. A browser fingerprint is a composite of dozens of
signals that together create a highly unique identifier — or, when analyzing bot traffic, a highly
consistent set of impossible or impossible-combination signals.
## 5.1  The Signal Taxonomy — Complete Reference
The following table documents the complete taxonomy of fingerprinting signals as established
in the academic literature, primarily from Laperdrix et al. (2020) "Browser Fingerprinting: A
Survey" in ACM Computing Surveys, and subsequent work:
## Categor
y
SignalAPI UsedExploitabi
lity
## Academic Reference
## Renderin
g
## Canvas
fingerprint
CanvasRendering
Context2D
## Very High
— unique
per
GPU/driver
## /OS
Mowery & Shacham (2012); "The
Web Never Forgets" (CCS 2014)
## Renderin
g
WebGL
renderer string
WEBGL_debug_r
enderer_info
## Very High
## — GPU
vendor/mo
del
exposed
directly
Cao et al. (2017)
## Renderin
g
WebGL shader
rendering
WebGLRendering
## Context
## High —
shader
output
varies per
## GPU
## Multiple (2018-2024)
## Renderin
g
AudioContext
fingerprint
OfflineAudioConte
xt
High — FP
arithmetic
varies per
hardware
## Englehardt & Narayanan (2016)
## Renderin
g
SVG / font
rendering
SVGTextContent
## Element
## Medium —
font metric
differences
per
platform
Laperdrix et al. (2016)
HardwareCPU core countnavigator.hardwar
eConcurrency
## Medium —
reveals
device
class
Sanchez-Rola et al. (2018)
HardwareDevice memorynavigator.deviceM
emory
## Low-
## Medium —
rounded to
nearest
power of 2
## Various
HardwareScreen
resolution
screen.width/
height
## Medium —
combined
with other
signals
Classic (EFF Panopticlick 2010)

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## Categor
y
SignalAPI UsedExploitabi
lity
## Academic Reference
HardwarePixel density
## (DPR)
window.devicePix
elRatio
## Medium —
differentiat
es
mobile/HiD
## PI
## Various
SoftwareUser-Agent
string
navigator.userAge
nt
Low alone
— easily
spoofed,
but cross-
checked
## Classic
SoftwareBrowser
language
navigator.languag
e
Low alone
— cross-
checked
with
## Accept-
## Language
header
## Various
SoftwareTimezoneIntl.DateTimeFor
mat
## Medium —
must
match IP
geolocatio
n
## Multiple
SoftwareInstalled fonts
list
Canvas text
measurement
## High —
large
entropy,
## ~400
distinguish
able fonts
## Fifield & Egelman (2015)
SoftwareBrowser pluginsnavigator.pluginsMedium —
empty in
headless =
detection
## Classic
SoftwareCookie/storage
support
document.cookie,
localStorage
## Low —
absence
flags
unusual
config
## Various
SoftwareCSS media
queries
matchMedia()Medium —
dark mode,
reduced
motion,
pointer
type
## Recent (2021-2024)
NetworkWebRTC IP
leak
RTCPeerConnecti
on
## Very High
— leaks
real IP
behind
proxy
Viejo et al. (2015)
NetworkTCP timing
patterns
## Indirect (via
timing)
## Medium —
datacenter
vs
residential
latency
## Various

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## Categor
y
SignalAPI UsedExploitabi
lity
## Academic Reference
DOMwindow.__webd
river_evaluate
Selenium injectionVery High
## —
definitive
## Selenium
signal
Industry standard
DOMcdc_ prefix
globals
ChromeDriver
injection
## Very High
## —
ChromeDri
ver
signature
Industry standard
DOMDOM mutation
timing
MutationObserverMedium —
plugin
modificatio
ns
detectable
Li et al. (2020)
5.2  How Canvas Fingerprinting Works in Detail
Canvas fingerprinting is the most powerful and widely deployed fingerprinting technique. The
principle exploits the fact that graphical rendering involves a chain of hardware and software
components, each of which introduces minute variations in the final output:
6.A JavaScript script draws text, shapes, gradients, and shadows onto an HTML
<canvas> element using specific drawing commands.
7.These commands pass through: the browser's rendering engine → the operating
system's 2D graphics library (e.g., Skia on Chrome/Linux, DirectWrite on Windows,
CoreGraphics on macOS) → the GPU driver.
8.Sub-pixel rendering, anti-aliasing algorithms, font hinting, gamma correction, and
floating-point rounding all differ between GPU/OS/driver combinations.
9.The script calls canvas.toDataURL() to extract the resulting pixel array as a base64-
encoded string.
10.This string is hashed to produce the canvas fingerprint.
The result: two machines with identical software but different GPU vendors produce different
hashes. Two instances of the same scraper tool on the same machine produce identical
hashes. The consistency of the hash across millions of requests immediately reveals
automation.
5.3  AudioContext Fingerprinting
AudioContext fingerprinting was discovered by researchers at Princeton in 2016 while
studying tracking mechanisms on the top 100,000 websites. The technique:
11.Create an OfflineAudioContext with a specified sample rate and buffer size.
12.Create an OscillatorNode generating a sine wave at a specific frequency.
13.Route it through a DynamicsCompressorNode with specific parameters.
14.Render to buffer and extract the resulting floating-point audio samples.
The floating-point arithmetic in the audio processing pipeline differs very slightly between CPU
architectures, audio library implementations, and operating systems. The resulting sample
values — typically around 35 decimal places — are effectively unique per hardware

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
configuration while being perfectly consistent across repeated measurements on the same
machine.
## 5.4  Detection Tools — The Academic Research Platforms
ToolPurposeGitHub
## Stars
Used InKey Capability
FingerprintJSVisitor ID / bot
detection library
~22kCommercial
products
Industry standard. Open-source
+ commercial Pro version with
## ML
CreepJSAggressive multi-
vector detector
~3.8kStealth
benchmarking
Lie detection, prototype
analysis, worker consistency,
100+ signals
OpenWPMAcademic fingerprint
measurement
~1.6kResearch
papers
Firefox instrumentation for mass
web measurement. Used in
most academic studies
fp-radarFingerprint analysis
research tool
~500Academic
research
Real-time fingerprint stream
analysis
## Fingerprint
## Insider
Signal inspection~300Research /
auditing
Visual breakdown of all
fingerprint dimensions

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 6 — Layer 5: Behavioral Biometrics and
## Human Movement Simulation
The final layer is the most nuanced and the most recently developed area of bot detection.
Rather than inspecting static properties of the browser environment, behavioral biometric
detection records and analyzes the sequence of user interactions: mouse movement,
keyboard typing, scrolling, and even page engagement patterns.
## 6.1  What Bot Detection Systems Measure
Modern   behavioral   analysis   platforms   (Cloudflare's   behavioral   analytics,   DataDome,
PerimeterX / HUMAN Security, and Shape Security) collect and analyze the following
interaction signals:
Signal CategoryWhat Is MeasuredBot IndicatorHuman
## Characteristic
Mouse trajectoryPath between pointsPerfectly straight lines;
teleportation
Curved paths with
natural acceleration
and deceleration
Mouse velocitySpeed profile along pathConstant velocity
throughout
Bell-curve velocity:
accelerate, peak,
decelerate near
target
Mouse accelerationRate of velocity changeZero or infinite
acceleration
Smooth acceleration
profile following
sigma log-normal
model
Click precisionDwell time on targetInstant click at exact
coordinates
Brief hover with
slight position jitter;
natural landing
Inter-Keystroke
Timing (IKT)
Time between keypressesPerfect uniform timingVariable: depends
on finger distance,
cognitive load,
common bigrams
Typing errors /
corrections
Error rate and correction
pattern
0% errors or scripted
errors
Natural error rate
~5-10%; corrections
via backspace
Scroll velocityScroll speed and
deceleration
Constant delta-Y
increments
## Momentum-based
deceleration; micro-
pauses at content
boundaries
Tab focus / blurWindow focus switchingZero focus eventsNatural multi-
tasking: focus lost
and regained during
real sessions
Time-on-pageDuration before first action< 500ms (bot) or perfectly
timed
Variable: 3-30s for
reading; correlated
with content length
Viewport interactionWhether user scrolls to
reveal content
No scroll (content above
fold)
Scroll pattern
correlated with page
layout

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
6.2  The Sigma Log-Normal Model — The Mathematics of Human
## Movement
The most important mathematical model in behavioral biometrics for mouse simulation is the
sigma log-normal model, first applied to handwriting analysis by Plamondon (1989) and
adapted to cursor movement by Feher et al. (2012) for continuous authentication research.
The model describes human hand movement as a superposition of velocity impulses, each
following a log-normal distribution:
v(t) = Σ Di × [Φ_ln(t; t0i, μi, σi) - Φ_ln(t; t0i, μi + Δμi, σi)]
## Where:
Di    = amplitude of the i-th velocity impulse
t0i   = time offset of the i-th impulse (motor command launch time)
μi    = log-mean parameter controlling peak timing
σi    = log-standard deviation (shape of the velocity bell)
Δμi   = duration parameter of the velocity pulse
Φ_ln  = log-normal cumulative distribution function
The neurophysiological basis: human voluntary movements are driven by a sequence of
muscle activation impulses from the neuromuscular system. Each impulse follows a log-
normal velocity profile due to the multiplicative nature of neural transmission delays. The sum
of these impulses produces the characteristic "accelerate, peak, decelerate" velocity profile
observed in all human cursor movements.
Key properties that make this model useful for simulation:
•The model generates statistically realistic mouse trajectories that are
indistinguishable from real human trajectories in frequency-domain analysis
•Parameters can be sampled from distributions derived from human motion capture
datasets
•The model naturally produces the speed-accuracy tradeoff described by Fitts' Law
•Adding appropriate noise and jitter at the sample level produces the micro-tremor
characteristic of real hand movement
6.3  Fitts' Law and Target Acquisition
Fitts' Law (1954) is a predictive model of human movement that describes the relationship
between movement time, target size, and target distance:
MT = a + b × log (2D / W)₂
## Where:
MT  = Movement Time (in seconds)
D   = Distance to the target
W   = Width of the target (size)
a,b = empirical constants (vary by user/device)
This has a critical practical implication: a bot that moves the cursor to a small, distant button too
quickly violates Fitts' Law. Real humans take longer to click small, distant targets. Any
movement that is "too fast" relative to the target geometry is a detectable anomaly.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## 6.4  Human Simulation Libraries
LibraryAlgorithm UsedGitHu
b
## Stars
## Supported
## Frameworks
## Notes
HumanCursorNatural motion +
variable
speed/curvature
~500Selenium
(Chrome, Edge)
Mouse click, drag, scroll,
hover with acceleration
profiles
HumanMoveMo
use
Sigma log-normal
model on 300 human
samples
~300GeneralStatistical model trained
on real trajectories +
minimum-jerk interpolation
HumanTypingMarkov Chain-based
keystroke model
~400Playwright,
## Selenium
Models errors, corrections,
fatigue, speed variation
per bigram
human-cursor-
trajectory
Sigma log-normal
mathematical model
~200GeneralGenerative model for
statistically
indistinguishable cursor
paths
robot-cppSmoothed movement
+ human timing
constants
C++ libSystem-levelTypeHumanLike() +
MoveSmooth(); double-
click, right-click, drag

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 7 — CAPTCHA Systems: Architecture,
Mechanisms, and Why They Are Failing
CAPTCHA (Completely Automated Public Turing test to tell Computers and Humans Apart)
has been the primary defense against automated access since 2003. Understanding how
modern CAPTCHA systems are architected — and why they continue to fail against
determined adversaries — is essential for both understanding the current state of the field and
designing better defenses.
## 7.1  Historical Evolution
EraMechanismDefeat MethodNotes
2003-2010Distorted text in
images (original
reCAPTCHA)
## OCR + CNN (>97%
accuracy by 2014)
Defeated so thoroughly CAPTCHA
books were published by 2012
2012-2018Image selection
challenges
(reCAPTCHA v2)
YOLOv8 object
detection (100%
accuracy, ETH Zurich
## 2024)
Required clicking all squares with
buses, traffic lights, etc.
## 2018-
present
Invisible / score-based
(reCAPTCHA v3)
Score manipulation via
behavioral mimicry
No challenge displayed; returns risk
score 0.0-1.0
## 2020-
present
Crowdsource labeling
(hCaptcha)
ML classification
(95.93% accuracy,
## IEEE 2021)
Also harvests image labeling data as
revenue model
## 2022-
present
Passive behavioral +
PoW (Cloudflare
## Turnstile)
Partially mitigated;
behavioral analysis
harder to defeat
Best current CAPTCHA; no image
challenges
7.2  How reCAPTCHA v2 Works
reCAPTCHA v2 operates on a multi-factor analysis system. When a user clicks "I am not a
robot," the following happens simultaneously:
15.Risk Assessment (Background): Before the checkbox click, Google has already been
collecting browser fingerprint, IP reputation, cookie history, behavioral signals from
the current page session, and User-Agent consistency data. This background data
shapes the challenge difficulty.
16.Checkbox Interaction Analysis: The trajectory and timing of the mouse click on the
checkbox is analyzed. A perfectly centered, instant click scores badly. A natural
approach path with micro-jitter scores well.
17.Image Challenge (if risk score is marginal): A grid of images is presented. The user
must select all squares containing a specific object. Critically, the challenge updates
dynamically as squares are selected — this tests interaction consistency across
multiple sequential clicks.
18.Timing Analysis of Challenge: Time taken to complete the challenge is analyzed. Too
fast (< 3 seconds) is bot-like. A realistic range is 8-30 seconds depending on
challenge difficulty. Some systems also analyze inter-click intervals within the
challenge.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## 7.3  How Cloudflare Turnstile Works
Cloudflare Turnstile represents the current state of the art in CAPTCHA design. It executes "a
rotating suite of non-intrusive browser challenges" that run invisibly in the background. Its
architecture involves multiple components operating in parallel:
•Proof-of-Work (PoW): A small computational puzzle is sent to the client. The browser
must compute a specific hash within tight parameters. This verifies computational
capability consistent with a real device. The PoW difficulty is calibrated to a human-
session time window — slow enough that it cannot be parallelized trivially, fast
enough that legitimate users don't notice.
•Cryptographic Attestation (Private Access Tokens): On Apple devices with iOS 16+,
Turnstile can request a hardware-attested token from the Secure Enclave. This
cryptographically proves the request comes from a real Apple device that has passed
Apple's own bot checks. Bots cannot generate valid Private Access Tokens.
•Behavioral Signal Collection: Mouse movement, keyboard events, scroll behavior,
and touch events (on mobile) are collected during the Turnstile execution window.
These are evaluated against the expected behavioral distribution for the detected
device type.
•Browser Integrity Checks: TLS fingerprint, HTTP/2 settings, navigator properties,
Canvas hash, WebGL renderer, AudioContext — all checked in the Turnstile script
execution context.
•IP Reputation and ASN Analysis: The connecting IP is checked against Cloudflare's
global threat intelligence database, which covers billions of requests per day.
7.4  CAPTCHA Defeat Rates — Academic Research Summary
CAPTCHA SystemAttack MethodAccuracySourceYear
## Text-based
CAPTCHA (all)
CNN + image
preprocessing
>97%Multiple academic
studies
## 2013-2018
reCAPTCHA v2YOLOv8 image
segmentation +
classification
## 100%
## (surpassing
humans)
ETH Zurich —
ResearchGate/ar
## Xiv
## 2024
hCaptcha (live sites)ML classification pipeline
on 270 live challenges
95.93% — avg
## 18.76s/challen
ge
## Hossen & Hei —
IEEE / arXiv
## 2021
Audio CAPTCHA
(reCAPTCHA)
Speech-to-text (Google
own API)
85%Kim et al. —
## NDSS
## 2016
## Reasoning-based
CAPTCHA (various)
LLM-based semantic
reasoning (GPT-4 class)
## 63.5%
average
Oedipus system
— arXiv
## 2024
Cloudflare TurnstileNo published public defeat
rate
Not publicly
broken
## Industry
observation
## 2024-2026
7.5  The Field Is Moving Away from CAPTCHAs
The academic research community and the industry have converged on a key insight:
CAPTCHAs are failing because they are fundamentally a discrete, visible challenge. The
future is continuous passive verification — collecting 50-100+ signals silently during normal
browsing to compute a real-time bot probability score. This is already the architecture of
reCAPTCHA v3 and Cloudflare's behavioral scoring. The challenge is no longer "prove you are

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
human before accessing this page" — it is "prove you behaved consistently like a human
across the last 5 minutes of interaction."

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 8 — Simple Evasion Tricks: Timing Delays and
## Basic Mimicry
Before   examining   sophisticated   multi-layer   evasion   architectures,   it   is   instructive   to
understand the simple tricks that work against naive, poorly designed CAPTCHA systems.
This understanding is valuable because it reveals exactly the weaknesses that basic
CAPTCHA implementations contain, and why modern systems moved beyond these
approaches.
## 8.1  The 45-60 Second Wait Trick
Some early and poorly designed CAPTCHA systems implemented a simple timing threshold: if
a form was submitted too quickly after the page loaded, it was flagged as a bot. The
assumption was that a human would take some time to read the page, fill in the form, and then
submit.
The bypass is trivially simple: insert a time.sleep(45) or time.sleep(60) call between page load
and form submission. The system observes that approximately one minute passed, interprets
this as human reading time, and allows the request through.
This worked against first-generation timing-only systems. It is essentially useless against any
modern bot detection for several reasons:
•Modern systems analyze interaction patterns during the wait period, not just the total
time. A 60-second wait with zero mouse movement, zero scroll events, and zero
keyboard input is not a human reading a page — it is a process that is sleeping.
•Cloudflare, DataDome, and similar systems expect to see micro-interactions during
the session. Even natural page reading generates mouse micromovements,
occasional scrolls, and window focus/blur events. A completely static session for 60
seconds is itself a bot signal.
•The timing distribution matters. Bots that implement random sleep(40 +
random.randint(0,30)) all cluster around the same distribution. Human timing follows
a much more complex distribution correlated with page content, reading speed, and
user intent.
8.2  User-Agent Rotation (and Why It Fails)
Rotating User-Agent strings was among the earliest evasion techniques. The logic: if each
request uses a different browser identifier, it looks like different users. This fails completely in
any system that implements cross-signal consistency checks, which all modern systems do:
•A User-Agent claiming to be "Chrome 124 on macOS" combined with a Windows-
characteristic TLS fingerprint is immediately inconsistent.
•A User-Agent claiming to be "Firefox 125" combined with a Canvas fingerprint
characteristic of headless Chromium is immediately inconsistent.
•Random rotation with no fingerprint matching produces a stream of random
mismatches that are arguably more bot-like than a consistent identity would be.
8.3  Simple IP Rotation (and Its Limits)
Basic IP rotation (switching between datacenter IPs on each request) is defeated by:
•ASN-level analysis: datacenter IP ranges are well-known and catalogued. A request
from an IP belonging to AWS, Google Cloud, Azure, or any known VPN provider is
immediately suspect.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
•Session consistency: a human session typically maintains the same IP for its
duration. A session that changes IP mid-flow is anomalous.
•Residential proxy detection: even residential IPs can be identified as proxy IPs
through timing analysis and database cross-referencing.
## 8.4  What These Simple Tricks Teach Us
Key Insight for Defenders
The reason these simple tricks fail is that they address only one signal in isolation. Modern
detection works because it aggregates dozens of signals simultaneously and looks for internal
consistency. A system that patches one leak perfectly while leaving ten others open is no more
secure than an unpatched system. This principle — consistency across all signals — is the core
design challenge for any sophisticated evasion system, and the core design requirement for
any sophisticated defense system.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 9 — Theoretical Multi-Layer Evasion
Architecture: A Threat Model for Defenders
## Academic Threat Model — Educational Purpose Only⚠
The following analysis is a conceptual threat model presented in the tradition of academic
security   research,   following   the   methodology   of   published   works   including   "Breaking
reCAPTCHAv2" (ETH Zurich, 2024), "A Low-Cost Attack Against the hCaptcha System"
(Hossen & Hei, IEEE 2021), and similar academic papers. Understanding the complete
theoretical attack surface is the prerequisite for designing effective countermeasures. No
implementation code is provided. Every component described here is derived from published
academic research or documented open-source tools. The goal is to show defenders what they
must protect against, and to demonstrate why each defensive layer is necessary.
9.1  The Core Problem: Cross-Layer Consistency
The central insight that must guide any serious analysis of this field: individual layers can each
be   addressed   by   existing   tools.   The   fundamental   unsolved   challenge   is   cross-layer
consistency. A theoretical comprehensive evasion system must generate a set of signals that
are not merely plausible independently, but internally coherent across all five dimensions
simultaneously.
Consider the constraints: if the theoretical system claims to be Chrome 124 on a Windows 11
laptop with an NVIDIA GPU:
•Layer 3 (TLS): Must produce a JA3/JA4 hash matching Chrome 124 on Windows,
with HTTP/2 SETTINGS matching the Chrome 124 HTTP/2 implementation
•Layer 4a (Browser): Navigator properties, plugin list, language, platform must all be
consistent with Chrome 124 / Windows 11
•Layer 4b (Canvas): Canvas rendering output must be consistent with an NVIDIA
GPU on Windows (specific driver characteristics)
•Layer 4c (WebGL): WEBGL_debug_renderer_info must return strings consistent with
an NVIDIA GPU, and shader rendering output must be plausible for that GPU class
•Layer 4d (AudioContext): AudioContext floating-point output must be consistent with
Windows audio pipeline on x86-64 hardware
•Layer 4e (Screen): Screen resolution, pixel ratio, and color depth must be consistent
with a real laptop screen (not headless defaults)
•Layer 5 (Behavior): Mouse movements must follow Fitts' Law for the rendered page
layout, typing speed must be consistent with human IKT distributions
Making all of these consistent simultaneously, across an arbitrarily large number of target
websites, without any single signal contradicting another, is the core engineering challenge.
This is why comprehensive evasion at scale remains a difficult research problem.
9.2  Technology Stack by Layer
A   theoretical   comprehensive   evasion   system   would   require   components   at   multiple
technology levels. The following describes the conceptual architecture based on the published
research on each component:
## ┌─────────────────────────────────────────────────────────────────────────┐
## │  LANGUAGE / TECHNOLOGY LAYERS IN A THEORETICAL EVASION STACK           │
## └─────────────────────────────────────────────────────────────────────────┘

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
C++ / C LAYER (Compiled Browser Binary)
├─ Modified browser source code (Camoufox/CloakBrowser approach)
├─ Remove headless detection signals at compile time
├─ Patch navigator property setters in C++
├─ Control Canvas/WebGL rendering paths at GPU API level
└─ Expose normal browser APIs identical to non-headless instance
RUST / Go LAYER (Network & TLS)
├─ curl-impersonate fork: TLS ClientHello construction matching target browser
├─ HTTP/2 SETTINGS frame values matching target browser implementation
├─ ALPN protocol negotiation matching target browser
└─ Connection timing and keep-alive parameters matching target browser
JAVASCRIPT LAYER (In-Browser Environment)
├─ Fingerprint consistency enforcement (redundant with C++ layer in binary-
patch approach)
├─ Worker scope consistency (consistent fingerprint in Web Workers)
├─ Prototype chain integrity preservation
└─ DOM event generation for natural interaction simulation
PYTHON / ORCHESTRATION LAYER (Session Management)
├─ Browser profile management (consistent cookies, history, localStorage)
├─ Proxy management (residential IP + geolocation consistency)
├─ Cross-session fingerprint consistency (same "device" across sessions)
├─ Behavioral simulation (sigma log-normal mouse + IKT keyboard)
└─ CAPTCHA timing and challenge response management
## 9.3  Conceptual Architecture Diagram
## ┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER (Python)                        │
│  Session State  │ Proxy/IP Rotation │ Consistency Verifier │ Recovery │
## └──────────────────────────────────┬──────────────────────────────────────┘
│ coordinates all sub-layers
## ┌─────────────────────────────────┼──────────────────────────────────────┐
## │                                 │                                      │
## ▼                                 ▼                                      ▼
┌───────────────┐        ┌──────────────────────┐        ┌─────────────────────┐
│  BEHAVIORAL   │        │   FINGERPRINT         │        │  CAPTCHA HANDLER    │
│  SIMULATION   │        │   CONSISTENCY         │        │                     │
│  LAYER        │        │   LAYER               │        │  Timing simulation  │
│               │        │                       │        │  (Fitts' Law based) │
│  Sigma-LN     │        │  GPU+screen+timezone  │        │  Challenge response │
│  mouse model  │        │  +fonts+plugins all   │        │  (ML classification │
│  IKT keyboard │        │  coherent together    │        │   for image types)  │
│  Fitts' Law  │        │  (same device profile)│        │                     │
└───────────────┘        └──────────────────────┘        └─────────────────────┘
## │                          │                                 │
## └──────────────────────────┼─────────────────────────────────┘
## │
## ┌─────────────────────▼──────────────────────────┐
## │             NETWORK IDENTITY LAYER             │
│  (Rust/Go — curl-impersonate approach)          │
## │                                                │
│  TLS/JA4 impersonation │ HTTP/2 SETTINGS match │
│  Residential proxy     │ Consistent geolocation│
│  ASN = real ISP        │ ALPN negotiation match│
## └─────────────────────┬──────────────────────────┘
## │
## ┌─────────────────────▼──────────────────────────┐
## │        BROWSER EXECUTION ENVIRONMENT           │
│  (C++ binary-patched browser — Camoufox/       │
│   CloakBrowser approach)                       │

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
## │                                                │
│  CDP signals removed at compile level          │
│  navigator.webdriver never set to true in C++  │
│  Headless rendering identical to headed        │
│  Real browser profile data (cookies, history)  │
## └────────────────────────────────────────────────┘
9.4  The Fundamental Challenge: Why This Is Hard at Scale
Even with all five layers addressed, several fundamental problems remain unsolved in the
research literature:
19.Hardware Attestation Gap: Cloudflare Turnstile can request a hardware-backed
Private Access Token from Apple devices. These tokens are signed by the device's
Secure Enclave and cannot be generated by software alone. Any evasion system
running on standard server hardware cannot produce valid attestation tokens. This is
a cryptographic hard wall.
20.Proof-of-Work Cost: Turnstile's PoW challenge is calibrated so that a single browser
solving it takes 50-200ms. At scale (100,000 requests/hour), the compute cost
becomes significant. This economic friction is a deliberate design choice.
21.Cross-Session Consistency: A consistent "device identity" across many sessions is
expensive to maintain. Using a different proxy per request but claiming the same
device fingerprint creates a geographically impossible device.
22.Real-Time Behavioral Analysis: Modern systems analyze behavioral patterns with
millisecond precision. The sigma log-normal model produces statistically realistic
trajectories but at the population level, ML classifiers may detect distribution
differences between generated and real behavior in large sample sets.
These limitations explain why commercial bypass services exist but are expensive, rate-
limited, and imperfect. The theoretical system described above represents a research-level
architecture, not a deployable product. Building and operating it at scale would require
significant engineering resources and would still be broken by hardware attestation on
compatible devices.

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
Chapter 10 — Complete Library Reference and
## Research Paper Catalog
10.1  Master Library Reference (All Categories)
LibraryCategoryLanguageGitHu
b
## Stars
Key Use CaseStatus
## (2026)
PlaywrightBrowser
## Automation
## Python/
## JS/.NET/
## Java
~67kModern browser
automation, network
interception
## Very
## Active
PuppeteerBrowser
## Automation
JavaScript/
## Node.js
~88kChrome/Firefox CDP
automation
## Very
## Active
SeleniumBrowser
## Automation
## Multi-
language
~31kLegacy; all browsers;
WebDriver standard
## Active
nodriverBrowser
## Automation
Python~8kMinimal CDP — wins
protocol-fingerprint
benchmarks
## Active
DrissionPageBrowser
## Automation
Python~12kHybrid
HTTP+browser mode
## Active
ScrapyHTTP SpiderPython~52kLarge-scale HTTP
crawling without JS
## Active
curl-cffiHTTP + TLSPython~13kHTTP with built-in
TLS impersonation
## Very
## Active
httpxHTTP AsyncPython~13kAsync HTTP/1+2,
pair with TLS tools
## Active
curl-
impersonate
## TLS
## Impersonation
C~16kBase library for
browser TLS
matching
## Active
tls-clientTLS
## Impersonation
Go~4kGo HTTP with TLS
fingerprint
impersonation
## Active
CamoufoxStealth
## Browser
Python/C+
## +
~8.4kFirefox C++ fork —
0% headless
detection
## Very
## Active
CloakBrowserStealth
## Browser
Python/C+
## +
## Trendin
g
Chromium C++ fork
— 49 binary patches
## New
## 2026
PatchrightStealth
## Browser
Python~3.2kPlaywright fork —
drops Runtime.enable
## Active
SeleniumBase
## UC
## Stealth
## Browser
Python~13kSelenium UC mode +
CDP mode
## Active
undetected-
chromedriver
## Stealth
## Browser
Python~41kPatched
ChromeDriver —
large community
## Active
FingerprintJSFingerprintingJavaScript~22kVisitor ID generation;
commercial Pro
version
## Active
CreepJSFingerprinting/JavaScript~3.8kMost aggressive Active

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
LibraryCategoryLanguageGitHu
b
## Stars
Key Use CaseStatus
## (2026)
Testingopen-source detector
— benchmark tool
OpenWPMFingerprint
## Research
## Python/
## Firefox
~1.6kAcademic web
measurement
platform
## Active
HumanCursorBehavioral
## Simulation
Python~500Natural cursor
movement for
## Selenium
## Active
HumanMoveM
ouse
## Behavioral
## Simulation
Python~300Sigma log-normal
model on human
trajectory data
## Active
HumanTypingBehavioral
## Simulation
Python~400Markov chain
keyboard simulation
for
Playwright/Selenium
## Active
## 10.2  Annotated Research Paper Catalog
## Browser Fingerprinting — Foundation Papers
PaperAuthors / Year /
## Venue
Key ContributionAvailable
"How Unique Is Your Web
Browser?" (Panopticlick)
Eckersley, EFF,
## 2010
Foundation paper. Showed
browser characteristics alone
identify ~94% of users uniquely.
Introduced entropy
measurement for fingerprinting.
EFF website;
## ACM DL
"The Web Never Forgets"Acar et al.,
Princeton / CCS
## 2014
Found Canvas fingerprinting on
5% of top 100k sites.
Discovered AudioContext
fingerprinting. Used OpenWPM
for measurement. Most-cited
field paper.
arXiv:1412.25
## 43
"FPRandom: Randomizing
## Core Browser Objects"
Laperdrix et al.,
## 2017
Introduced moving target
defense — randomized browser
environments to prevent
fingerprinting. Proves
randomization is an effective
partial countermeasure.
ACM Digital
## Library
"Browser Fingerprinting: A
## Survey"
Laperdrix et al.,
ACM Computing
## Surveys, 2020
Comprehensive survey of the
entire field. Best entry point for
newcomers. Covers all signal
types, all defenses, all attacks
up to 2020.
ACM DL (open
access)
"Automatic Discovery of
## Emerging Browser
## Fingerprinting
## Techniques"
Multiple authors,
## ACM WWW 2023
Uses taint tracking to
automatically identify new
fingerprinting behaviors in the
wild. Shows the field is
continuously evolving.
## ACM DL 2023

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
PaperAuthors / Year /
## Venue
Key ContributionAvailable
"Byte by Byte: Unmasking
Browser Fingerprinting at
## Function Level Using V8
## Bytecode Transformers"
Multiple authors,
## CCS 2025
## State-of-the-art. Uses
Transformer models on V8
bytecode to identify
fingerprinting functions with
obfuscation resilience.
arXiv 2025
CAPTCHA and Bot Detection — Key Papers
PaperAuthors / Year /
## Venue
Key ResultAvailable
"Breaking
reCAPTCHAv2"
ETH Zurich
researchers, 2024
100% solve rate on reCAPTCHA
v2 using YOLOv8. Previous best
was 68-71%. No statistically
significant difference in
challenge count between
humans and the ML system.
arXiv /
ResearchGate
## 2024
"A Low-Cost Attack
against the hCaptcha
## System"
Hossen & Hei, IEEE
## 2021
95.93% accuracy on 270 live
hCaptcha challenges. Average
solve time 18.76 seconds.
Evaluated against live websites,
not a lab simulation.
arXiv:2104.076
## 22; IEEE
"Oedipus: LLM-
## Enhanced Reasoning
CAPTCHA Solver"
Multiple authors, 202463.5% average success rate.
Introduces LLM-based
reasoning for CAPTCHAs
requiring semantic
understanding rather than visual
classification.
arXiv 2024
"I'm Not a Human:
Breaking the Google
reCAPTCHA"
Kim et al., NDSS 2016Used audio CAPTCHA +
Google's own Speech API to
achieve 85% solve rate on audio
challenges. Classic paper on
CAPTCHA audio bypass.
## NDSS 2016
proceedings
"Measuring Users'
Frustration with
reCAPTCHA"
Multiple authors, 2023Users wasted 819 million hours
on 512 billion reCAPTCHA v2
sessions. Established user
burden quantification for
CAPTCHAs.
## Various 2023
## Behavioral Biometrics
PaperAuthors /
## Year
Key ContributionRelevance
"Mouse Dynamics as a
Behavioral Biometric for
## Authentication"
## Multiple
authors,
various
Establishes mouse trajectory,
velocity, and acceleration as
authentication signals.
Foundation of behavioral bot
detection.
Direct basis for
Layer 5 bot
detection
"Continuous
## Authentication Using
## Mouse Dynamics"
Feher et al.Proposes sigma log-normal
velocity model for synthetic
mouse trajectory generation.
Core model for
human simulation

The Anti-Bot Arms Race — Technical Research Monograph 2026
## Page
PaperAuthors /
## Year
Key ContributionRelevance
Mathematical foundation for
HumanMoveMouse library.
"Modeling Motor Activity
Timing as an Individual
## Characteristic"
## Plamondon,
## 1989+
Original sigma log-normal model
for voluntary movement.
Neurophysiological basis:
neuromuscular system
generates log-normal impulses.
## Mathematical
foundation of the
field