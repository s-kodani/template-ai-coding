"""Exercise native send behavior without accepting unrelated dialogs."""

from __future__ import annotations

from conftest import send_chat
from playwright.sync_api import Page, expect


def test_send_chat_closes_only_the_native_update_notice(page: Page) -> None:
    page.set_default_timeout(1000)
    page.set_content('''
        <textarea id="chat-input" aria-label="Message"></textarea>
        <button id="send-message-button" onclick="send()">Send message</button>
        <div class="absolute bottom-8 right-8 z-50"
             style="position:fixed;inset:0;background:lightblue">
          A new version is now available.
          <a href="https://github.com/open-webui/open-webui/releases">Update for the latest features.</a>
          <button aria-label="Close" onclick="this.parentElement.remove()">Close</button>
        </div>
        <section role="dialog" aria-label="Tool call confirmation">
          <button aria-label="Close" onclick="this.parentElement.remove()">Close</button>
          <button onclick="window.permissionAccepted = true">Confirm</button>
        </section>
        <script>
          function send() {
            const reply = document.createElement('div');
            reply.className = 'chat-assistant';
            const content = document.createElement('div');
            content.id = 'response-content-container';
            content.textContent = document.getElementById('chat-input').value;
            reply.append(content);
            document.body.append(reply);
          }
        </script>
    ''')

    reply = send_chat(page, "second turn", timeout_ms=1000)

    expect(reply).to_contain_text("second turn")
    expect(page.get_by_role("dialog", name="Tool call confirmation")).to_be_visible()
    assert not page.evaluate("Boolean(window.permissionAccepted)")
    expect(page.locator('a[href="https://github.com/open-webui/open-webui/releases"]')).to_have_count(0)
