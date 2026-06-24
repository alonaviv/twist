#!/usr/bin/env python3
"""
Generates money-time.jmx — a JMeter 5.6 plan that reproduces the BWT "money time":
  * 40 singers logging in and submitting a song at the SAME instant (rendezvous)
  * 60 audience members loading the room and polling
  * everyone then polls the live endpoints at the real browser cadence
  * pass/fail benchmarks via a per-request response-time SLA + HTTP-200 assertion

All knobs are -J properties so the same file runs from a laptop or a cloud box and
against any tier without editing.  See README block printed at the bottom.
"""

# --- logical poll sets, taken from the real frontend setInterval() calls -------
# home.js populateSpotlight @1s: /evening_started then /next_singer (pre-start) or /spotlight_data
# home.js populateDashboard @1s: /dashboard_data  -- ONLY if isSinger (audience never calls it)
# base.js getQuestion @0.5s (every logged-in page): /get_active_question  (always 200, {} when no trivia)
#   -> when a trivia question is active it ALSO polls /get_selected_answer @0.5s; that 404s with no
#      active trivia, so it is NOT part of money-time. Run a separate trivia scenario for that peak.
# add-song.js checkDisableSignup @0.5s: /signup_disabled -- ONLY while on the /add_song page (brief)
SINGER_POLLS = [
    "/evening_started", "/next_singer", "/spotlight_data", "/dashboard_data",
    "/get_active_question", "/get_active_question",   # the 0.5s base poll, doubled
]
AUDIENCE_POLLS = [
    "/evening_started", "/next_singer", "/spotlight_data",
    "/get_active_question", "/get_active_question",    # no /dashboard_data: isSinger-gated
]

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))

def node(xml, children=None):
    """A test-element + its hashTree of children."""
    if not children:
        return xml + "\n<hashTree/>\n"
    inner = "".join(render(c) for c in children)
    return xml + "\n<hashTree>\n" + inner + "</hashTree>\n"

def render(n):
    return node(n[0], n[1])

# ---------- element builders ---------------------------------------------------
def udv(name, pairs):
    args = ""
    for k, v in pairs:
        args += f'''<elementProp name="{k}" elementType="Argument">
  <stringProp name="Argument.name">{k}</stringProp>
  <stringProp name="Argument.value">{esc(v)}</stringProp>
  <stringProp name="Argument.metadata">=</stringProp>
</elementProp>'''
    return (f'<Arguments guiclass="ArgumentsPanel" testclass="Arguments" testname="{name}" enabled="true">'
            f'<collectionProp name="Arguments.arguments">{args}</collectionProp></Arguments>', [])

def http_defaults():
    return ('''<ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP Request Defaults" enabled="true">
  <elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments"/></elementProp>
  <stringProp name="HTTPSampler.domain">${HOST}</stringProp>
  <stringProp name="HTTPSampler.protocol">${PROTOCOL}</stringProp>
  <stringProp name="HTTPSampler.port">${PORT}</stringProp>
  <stringProp name="HTTPSampler.connect_timeout">10000</stringProp>
  <stringProp name="HTTPSampler.response_timeout">30000</stringProp>
</ConfigTestElement>''', [])

def cookie_mgr():
    return ('''<CookieManager guiclass="CookiePanel" testclass="CookieManager" testname="HTTP Cookie Manager" enabled="true">
  <collectionProp name="CookieManager.cookies"/>
  <boolProp name="CookieManager.clearEachIteration">false</boolProp>
  <boolProp name="CookieManager.controlledByThreadGroup">false</boolProp>
</CookieManager>''', [])

def header_mgr():
    return ('''<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="HTTP Header Manager" enabled="true">
  <collectionProp name="HeaderManager.headers">
    <elementProp name="" elementType="Header"><stringProp name="Header.name">Referer</stringProp><stringProp name="Header.value">${PROTOCOL}://${HOST}/</stringProp></elementProp>
    <elementProp name="" elementType="Header"><stringProp name="Header.name">Origin</stringProp><stringProp name="Header.value">${PROTOCOL}://${HOST}</stringProp></elementProp>
  </collectionProp>
</HeaderManager>''', [])

def get(path, children=None):
    return (f'''<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="GET {path}" enabled="true">
  <elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments"/></elementProp>
  <stringProp name="HTTPSampler.path">{path}</stringProp>
  <stringProp name="HTTPSampler.method">GET</stringProp>
  <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
  <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
</HTTPSamplerProxy>''', children or [])

def post(path, fields, children=None):
    args = ""
    for k, v in fields:
        args += f'''<elementProp name="{k}" elementType="HTTPArgument">
  <boolProp name="HTTPArgument.always_encode">true</boolProp>
  <stringProp name="Argument.value">{esc(v)}</stringProp>
  <stringProp name="Argument.metadata">=</stringProp>
  <boolProp name="HTTPArgument.use_equals">true</boolProp>
  <stringProp name="Argument.name">{k}</stringProp>
</elementProp>'''
    return (f'''<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="POST {path}" enabled="true">
  <elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments">{args}</collectionProp></elementProp>
  <stringProp name="HTTPSampler.path">{path}</stringProp>
  <stringProp name="HTTPSampler.method">POST</stringProp>
  <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
  <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
  <boolProp name="HTTPSampler.postBodyRaw">false</boolProp>
  <stringProp name="HTTPSampler.contentEncoding">UTF-8</stringProp>
</HTTPSamplerProxy>''', children or [])

def csv_dataset(name, filename, variables):
    return (f'''<CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="{name}" enabled="true">
  <stringProp name="filename">{filename}</stringProp>
  <stringProp name="fileEncoding">UTF-8</stringProp>
  <stringProp name="variableNames">{variables}</stringProp>
  <boolProp name="ignoreFirstLine">false</boolProp>
  <stringProp name="delimiter">,</stringProp>
  <boolProp name="quotedData">true</boolProp>
  <boolProp name="recycle">true</boolProp>
  <boolProp name="stopThread">false</boolProp>
  <stringProp name="shareMode">shareMode.all</stringProp>
</CSVDataSet>''', [])

def loop_controller(name, loops_expr, children):
    return (f'''<LoopController guiclass="LoopControlPanel" testclass="LoopController" testname="{name}" enabled="true">
  <boolProp name="LoopController.continue_forever">false</boolProp>
  <stringProp name="LoopController.loops">{loops_expr}</stringProp>
</LoopController>''', children)

def json_extractor(refname, path, default):
    return (f'''<JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="Extract {refname}" enabled="true">
  <stringProp name="JSONPostProcessor.referenceNames">{refname}</stringProp>
  <stringProp name="JSONPostProcessor.jsonPathExprs">{esc(path)}</stringProp>
  <stringProp name="JSONPostProcessor.match_numbers">1</stringProp>
  <stringProp name="JSONPostProcessor.defaultValues">{default}</stringProp>
</JSONPostProcessor>''', [])

def put_json(path, body, headers):
    hdrs = ""
    for k, v in headers:
        hdrs += f'<elementProp name="" elementType="Header"><stringProp name="Header.name">{k}</stringProp><stringProp name="Header.value">{esc(v)}</stringProp></elementProp>'
    hm = (f'''<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="JSON + CSRF headers" enabled="true">
  <collectionProp name="HeaderManager.headers">{hdrs}</collectionProp>
</HeaderManager>''', [])
    return (f'''<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="PUT {path}" enabled="true">
  <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>
  <elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments">
    <elementProp name="" elementType="HTTPArgument">
      <boolProp name="HTTPArgument.always_encode">false</boolProp>
      <stringProp name="Argument.value">{esc(body)}</stringProp>
      <stringProp name="Argument.metadata">=</stringProp>
    </elementProp>
  </collectionProp></elementProp>
  <stringProp name="HTTPSampler.path">{path}</stringProp>
  <stringProp name="HTTPSampler.method">PUT</stringProp>
  <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
  <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
  <stringProp name="HTTPSampler.contentEncoding">UTF-8</stringProp>
</HTTPSamplerProxy>''', [hm])

def csrf_extractor():
    # Scrape the hidden form field (works on pages that have {% csrf_token %} in a form)
    return ('''<RegexExtractor guiclass="RegexExtractorGui" testclass="RegexExtractor" testname="Extract csrfmiddlewaretoken" enabled="true">
  <stringProp name="RegexExtractor.useHeaders">false</stringProp>
  <stringProp name="RegexExtractor.refname">csrf</stringProp>
  <stringProp name="RegexExtractor.regex">name=&quot;csrfmiddlewaretoken&quot; value=&quot;([^&quot;]+)&quot;</stringProp>
  <stringProp name="RegexExtractor.template">$1$</stringProp>
  <stringProp name="RegexExtractor.default">CSRF_NOT_FOUND</stringProp>
  <stringProp name="RegexExtractor.match_number">1</stringProp>
</RegexExtractor>''', [])

def csrf_cookie_extractor():
    # Extract csrftoken from the Set-Cookie response header after login.
    # Django rotates the session (and thus the cookie) on login, so this gives the
    # definitive post-login token — used as a fallback for threads that may not reach
    # GET /add_song before the rendezvous fires.
    return ('''<RegexExtractor guiclass="RegexExtractorGui" testclass="RegexExtractor" testname="Extract csrf from cookie" enabled="true">
  <stringProp name="RegexExtractor.useHeaders">true</stringProp>
  <stringProp name="RegexExtractor.refname">csrf</stringProp>
  <stringProp name="RegexExtractor.regex">csrftoken=([^;]+)</stringProp>
  <stringProp name="RegexExtractor.template">$1$</stringProp>
  <stringProp name="RegexExtractor.default">CSRF_NOT_FOUND</stringProp>
  <stringProp name="RegexExtractor.match_number">1</stringProp>
</RegexExtractor>''', [])

def jsr223_assertion(name, script):
    return (f'''<JSR223Assertion guiclass="TestBeanGUI" testclass="JSR223Assertion" testname="{name}" enabled="true">
  <stringProp name="scriptLanguage">groovy</stringProp>
  <stringProp name="script">{esc(script)}</stringProp>
</JSR223Assertion>''', [])

def setup_thread_group(body):
    tg = '''<SetupThreadGroup guiclass="SetupThreadGroupGui" testclass="SetupThreadGroup" testname="Preflight checks (config + one login)" enabled="true">
  <stringProp name="ThreadGroup.on_sample_error">stoptest</stringProp>
  <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller">
    <boolProp name="LoopController.continue_forever">false</boolProp>
    <intProp name="LoopController.loops">1</intProp>
  </elementProp>
  <stringProp name="ThreadGroup.num_threads">1</stringProp>
  <stringProp name="ThreadGroup.ramp_time">1</stringProp>
  <boolProp name="ThreadGroup.scheduler">false</boolProp>
</SetupThreadGroup>'''
    return (tg, body)

def preflight():
    csrf_check = jsr223_assertion(
        "Assert CSRF token found (EVENT_SKU + PASSCODE must be set)",
        'if (vars.get("csrf") == "CSRF_NOT_FOUND") {\n'
        '    AssertionResult.setFailure(true);\n'
        '    AssertionResult.setFailureMessage("No csrfmiddlewaretoken on /login — '
        'set EVENT_SKU and PASSCODE in Constance admin before running");\n'
        '}'
    )
    login_ok = jsr223_assertion(
        "Assert login succeeded (not redirected back to /login)",
        'def loc = prev.getRedirectLocation() ?: "";\n'
        'def code = prev.getResponseCode();\n'
        'if (code == "403") {\n'
        '    AssertionResult.setFailure(true);\n'
        '    AssertionResult.setFailureMessage("POST /login returned 403 — CSRF or config problem");\n'
        '} else if (loc.contains("/login")) {\n'
        '    AssertionResult.setFailure(true);\n'
        '    AssertionResult.setFailureMessage("POST /login redirected back to /login — wrong PASSCODE or FREEBIE_TICKET");\n'
        '}'
    )
    signup_ok = jsr223_assertion(
        "Assert add_song_request succeeded",
        'def code = prev.getResponseCode();\n'
        'if (code != "200") {\n'
        '    AssertionResult.setFailure(true);\n'
        '    AssertionResult.setFailureMessage("POST /add_song_request returned " + code + " — check CAN_SIGNUP flag and singer auth");\n'
        '}'
    )
    return setup_thread_group([
        get("/login", [csrf_extractor(), csrf_check]),
        post("/login", [
            ("ticket-type", "singer"),
            ("first-name", "Preflight"),
            ("last-name", "Check"),
            ("passcode", "${PASSCODE}"),
            ("order-id", "${FREEBIE}"),
            ("no-upload", "on"),
            ("csrfmiddlewaretoken", "${csrf}"),
        ], [csrf_cookie_extractor(), login_ok]),
        get("/add_song", [csrf_extractor()]),
        post("/add_song_request", [
            ("song-name", "preflight"),
            ("musical", "Preflight Musical"),
            ("notes", "preflight"),
            ("csrfmiddlewaretoken", "${csrf}"),
        ], [signup_ok]),
    ])

def sync_timer():
    return ('''<SyncTimer guiclass="TestBeanGUI" testclass="SyncTimer" testname="Rendezvous - all singers submit at once" enabled="true">
  <intProp name="groupSize">0</intProp>
  <longProp name="timeoutInMs">30000</longProp>
</SyncTimer>''', [])

def pause_timer():
    # Attached to one sampler => one pause per loop iteration (the poll interval).
    return ('''<UniformRandomTimer guiclass="UniformRandomTimerGui" testclass="UniformRandomTimer" testname="Poll interval" enabled="true">
  <stringProp name="ConstantTimer.delay">${POLL_INTERVAL}</stringProp>
  <stringProp name="RandomTimer.range">200</stringProp>
</UniformRandomTimer>''', [])

def duration_assertion():
    return ('''<DurationAssertion guiclass="DurationAssertionGui" testclass="DurationAssertion" testname="SLA: response under ${SLA_MS} ms" enabled="true">
  <stringProp name="DurationAssertion.duration">${SLA_MS}</stringProp>
</DurationAssertion>''', [])

def code_assertion():
    return ('''<ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="HTTP 200" enabled="true">
  <collectionProp name="Asserion.test_strings"><stringProp name="49586">200</stringProp></collectionProp>
  <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>
  <boolProp name="Assertion.assume_success">false</boolProp>
  <intProp name="Assertion.test_type">8</intProp>
  <stringProp name="Assertion.custom_message"></stringProp>
</ResponseAssertion>''', [])

def thread_group(name, threads_prop, ramp_prop, body):
    tg = f'''<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="{name}" enabled="true">
  <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
  <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller">
    <boolProp name="LoopController.continue_forever">false</boolProp>
    <intProp name="LoopController.loops">-1</intProp>
  </elementProp>
  <stringProp name="ThreadGroup.num_threads">{threads_prop}</stringProp>
  <stringProp name="ThreadGroup.ramp_time">{ramp_prop}</stringProp>
  <boolProp name="ThreadGroup.scheduler">true</boolProp>
  <stringProp name="ThreadGroup.duration">${{DURATION}}</stringProp>
  <stringProp name="ThreadGroup.delay">0</stringProp>
  <boolProp name="ThreadGroup.same_user_on_next_iteration">true</boolProp>
</ThreadGroup>'''
    return (tg, body)

# ---------- login / signup once-only chains -----------------------------------
def login_chain(ticket_type, first_name):
    last = "${RUN_ID}n${__threadNum}"
    return [
        get("/login", [csrf_extractor()]),
        post("/login", [
            ("ticket-type", ticket_type),
            ("first-name", first_name),
            ("last-name", last),
            ("passcode", "${PASSCODE}"),
            ("order-id", "${FREEBIE}"),
            ("no-upload", "on"),
            ("csrfmiddlewaretoken", "${csrf}"),
        ], [csrf_cookie_extractor()]),
        get("/home"),
    ]

def singer_once_only():
    # 1) log in (clustered via ramp)  2) warm up on /home polling like a real waiting crowd
    # 3) open /add_song & poll signup_disabled  4) RENDEZVOUS -> all submit a short name at once
    # 5) edit the name to the real song afterwards (manage_songs -> get_current_songs -> update_song)
    warmup = loop_controller("Warm-up polling on /home (before the burst)",
                             "${WARMUP_LOOPS}", poll_batch(SINGER_POLLS))
    # Rename to a REAL song from songs.csv (distinct per thread) so SongRequest.save() re-fires
    # get_lyrics -> exa.ai actually searches for real lyrics. ${song}/${musical} come from the CSV.
    edit_body = (
        '{"song_id": ${songid}, "song_name": "${song}", '
        '"musical": "${musical}", "notes": "loadtest", "partners": []}'
    )
    body = login_chain("singer", "Loadsinger") + [
        warmup,
        get("/add_song", [csrf_extractor()]),
        get("/signup_disabled"),
        sync_timer(),
        # the simultaneous burst: short name typed fast ("ready, set, go")
        post("/add_song_request", [
            ("song-name", "${__threadNum}"),
            ("musical", "Loadtest Musical"),
            ("notes", "loadtest"),
            ("csrfmiddlewaretoken", "${csrf}"),
        ]),
        # ...then edit to the real song name (staggered, as each singer finishes)
        get("/manage_songs"),
        get("/get_current_songs", [json_extractor("songid", "$[0].id", "SONGID_NOT_FOUND")]),
        put_json("/update_song", edit_body,
                 [("X-CSRFToken", "${csrf}"), ("Content-Type", "application/json")]),
    ]
    return ('<OnceOnlyController guiclass="OnceOnlyControllerGui" testclass="OnceOnlyController" testname="Login + warm-up + simultaneous signup + edit (once per user)" enabled="true"/>', body)

def audience_once_only():
    return ('<OnceOnlyController guiclass="OnceOnlyControllerGui" testclass="OnceOnlyController" testname="Login (once per user)" enabled="true"/>',
            login_chain("audience", "Loadaudience"))

def poll_batch(paths):
    out = []
    for i, p in enumerate(paths):
        out.append(get(p, [pause_timer()] if i == 0 else None))
    return out

# ---------- assemble -----------------------------------------------------------
def build():
    config = udv("Config", [
        ("HOST",          "${__P(host,broadwaywithatwist.xyz)}"),
        ("PROTOCOL",      "${__P(protocol,https)}"),
        ("PORT",          "${__P(port,443)}"),
        ("PASSCODE",      "${__P(passcode,dev)}"),
        ("FREEBIE",       "${__P(freebie,123456)}"),
        ("DURATION",      "${__P(duration,300)}"),
        ("WARMUP_LOOPS",  "${__P(warmup,8)}"),
        ("POLL_INTERVAL", "${__P(poll_interval,1000)}"),
        ("SLA_MS",        "${__P(sla,2000)}"),
        ("RUN_ID",        "${__P(run_id,run${__time(YMDHMS)})}"),
        ("SONGS_CSV",     "${__P(songs_csv,songs.csv)}"),
    ])

    singers = thread_group("Singers (login + simultaneous signup + poll)",
                           "${__P(singers,40)}", "${__P(ramp,1)}",
                           [csv_dataset("Real songs (for lyrics/exa)", "${SONGS_CSV}", "song,musical"),
                            singer_once_only()] + poll_batch(SINGER_POLLS) +
                           [duration_assertion(), code_assertion()])

    audience = thread_group("Audience (login + poll)",
                            "${__P(audience,60)}", "${__P(ramp_aud,3)}",
                            [audience_once_only()] + poll_batch(AUDIENCE_POLLS) +
                            [duration_assertion(), code_assertion()])

    plan_children = [config, http_defaults(), cookie_mgr(), header_mgr(), preflight(), singers, audience]

    comments = esc(
        "BWT MONEY-TIME LOAD TEST  (40 singers sign up at once + 60 audience polling = 100 concurrent)\n"
        "\n"
        "BEFORE RUNNING, configure a throwaway event from OUTSIDE (browser admin / People's-Choice admin):\n"
        "  - Constance PASSCODE        = dev\n"
        "  - Constance EVENT_SKU       = LOADTEST   (any non-empty value; required to open the app)\n"
        "  - Constance FREEBIE_TICKET  = 123456     (must match the hardcoded order-id below)\n"
        "  - Enable feature flag CAN_SIGNUP\n"
        "These match the hardcoded defaults in this plan, so you can just hit Run with no -J flags.\n"
        "Override any of them with -Jpasscode= -Jfreebie= etc. if you change the event.\n"
        "\n"
        "RUN (headless, with HTML dashboard + pass/fail):\n"
        "  jmeter -n -t money-time.jmx -Jrun_id=$(date +%s) -l result.jtl -e -o report\n"
        "  python3 verdict.py result.jtl        # PASS/FAIL vs SLA\n"
        "\n"
        "FLOW per singer: login (clustered via ramp) -> warm up polling on /home (-Jwarmup loops) ->\n"
        "  open /add_song -> RENDEZVOUS (all 40 wait) -> POST /add_song_request with a short name typed\n"
        "  fast ('ready set go') -> then edit to the real name (manage_songs/get_current_songs/update_song).\n"
        "Audience just log in and poll. Trivia: /get_active_question is always polled; /get_selected_answer\n"
        "only fires during an ACTIVE trivia round (404s otherwise) so it is a separate scenario, not money-time.\n"
        "LYRICS/EXA: the edit renames to a real song from songs.csv (distinct per singer), which re-fires the\n"
        "get_lyrics celery task -> exa.ai really searches. So ~40 real lyric fetches per run (uses Exa quota).\n"
        "Keep songs.csv next to the jmx (scp it to bwt-stress too); override path with -Jsongs_csv=.\n"
        "\n"
        "KNOBS: -Jsingers=40 -Jaudience=60 -Jduration=300 -Jramp=1 -Jwarmup=8 -Jsla=2000 -Jpoll_interval=1000\n"
        "       -Jhost=broadwaywithatwist.xyz -Jrun_id=<unique each run, avoids 'already logged in'>\n"
        "Run the laptop only as a small functional check (e.g. -Jsingers=5 -Jaudience=5 -Jduration=30);\n"
        "do the real 100-user tier benchmark from the bwt-stress EC2 box (in-region). Reset the DB when done."
    )
    testplan = f'''<TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="BWT Money Time" enabled="true">
  <stringProp name="TestPlan.comments">{comments}</stringProp>
  <boolProp name="TestPlan.functional_mode">false</boolProp>
  <boolProp name="TestPlan.tearDown_on_shutdown">true</boolProp>
  <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
  <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
    <collectionProp name="Arguments.arguments"/>
  </elementProp>
  <stringProp name="TestPlan.user_define_classpath"></stringProp>
</TestPlan>'''

    body = "".join(render(c) for c in plan_children)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">\n<hashTree>\n'
            + testplan + "\n<hashTree>\n" + body + "</hashTree>\n</hashTree>\n</jmeterTestPlan>\n")

if __name__ == "__main__":
    open("money-time.jmx", "w").write(build())
    print("wrote money-time.jmx")
