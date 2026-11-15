"""Exercise the streaming regression's observer without a model or running stack."""
from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page
from test_mcp_app import _check_streaming_app


@pytest.mark.parametrize(
    ("scenario", "error"),
    [
        ("another-app", None),
        ("another-app-same-reply", None),
        ("initial-apps", None),
        ("refetch", "resource"),
        ("refetch-with-another-app", "resource"),
        ("replace", "App"),
        ("reload", "document"),
        ("reload-slow-baseline", "document"),
    ],
)
def test_streaming_observer_distinguishes_app_lifetimes(
    page: Page, monkeypatch: pytest.MonkeyPatch, scenario: str, error: str | None,
) -> None:
    page.route("http://mcp-app-test.invalid/**", lambda route: route.fulfill(body="{}"))
    page.goto("http://mcp-app-test.invalid/")
    page.set_content('''
        <textarea id="chat-input"></textarea>
        <button id="send-message-button" onclick="send()">Send</button>
        <button id="stop" aria-label="Stop" style="display:none">Stop</button>
        <script>
          let turns = 0;
          const appHtml = '<ul id="results"><li>seed</li></ul>';
          function resource() {
            return fetch('/api/v1/tools/id/server%3Amcp%3Aknowledge/mcp/app/rpc', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({
                method: 'ui/resource', binding: 'shared-server-tool-binding',
                tool_name: 'search_knowledge', params: {}
              })
            });
          }
          function mount(parent) {
            const container = document.createElement('div');
            const frame = document.createElement('iframe');
            frame.title = 'search_knowledge';
            frame.srcdoc = appHtml;
            container.append(frame);
            parent.append(container);
            resource();
            return frame;
          }
          function send() {
            const reply = document.createElement('div');
            reply.className = 'chat-assistant';
            const text = document.createElement('div');
            text.id = 'response-content-container';
            text.textContent = 'Ready';
            reply.append(text);
            document.body.append(reply);
            if (++turns === 1) return;
            const frame = mount(reply);
            if (window.scenario === 'initial-apps') mount(reply);
            document.getElementById('stop').style.display = 'block';
            let updates = 0;
            window.startScenario = () => { const timer = setInterval(() => {
              if (++updates === 1) {
                if (window.scenario === 'another-app') {
                  mount(document.querySelector('.chat-assistant'));
                } else if (window.scenario === 'another-app-same-reply') {
                  mount(reply);
                } else if (window.scenario === 'refetch') {
                  resource();
                } else if (window.scenario === 'refetch-with-another-app') {
                  mount(reply);
                  resource();
                } else if (window.scenario === 'replace') {
                  // Svelte keeps an exiting frame connected during its outro.
                  frame.parentElement.inert = true;
                  mount(reply);
                } else if (window.scenario.startsWith('reload')) {
                  frame.srcdoc = appHtml + '<p>New document</p>';
                }
              }
              text.textContent += ' streamed text';
              if (updates === 6) {
                clearInterval(timer);
                document.getElementById('stop').style.display = 'none';
              }
            }, 500); };
          }
        </script>
    ''')
    page.evaluate("scenario => window.scenario = scenario", scenario)
    if scenario == "reload-slow-baseline":
        element_handle = Locator.element_handle

        def delayed_handle(locator: Locator, **kwargs):
            if locator.evaluate("element => element.tagName") == "HTML":
                # Deliberately exceed the old scenario's 500ms startup delay.
                page.wait_for_timeout(800)
            return element_handle(locator, **kwargs)

        monkeypatch.setattr(Locator, "element_handle", delayed_handle)

    def check_streaming() -> None:
        _check_streaming_app(page, on_app_ready=lambda: page.evaluate("startScenario()"))

    if error is None:
        check_streaming()
    else:
        with pytest.raises(AssertionError, match=error):
            check_streaming()
