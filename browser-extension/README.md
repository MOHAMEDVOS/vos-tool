# VOS ReadyMode Browser Connector

This Chrome extension lets the VOS Audit page use ReadyMode sessions already signed in in this Chrome profile. It does not sign in or read cookie values. It fetches the selected call recordings and sends them to VOS for the existing audit analysis.

## Install for local testing

1. Open `chrome://extensions` in Chrome.
2. Turn on **Developer mode**.
3. Choose **Load unpacked** and select this `browser-extension` folder.
4. Reload the VOS Audit page.

To update an already loaded copy, click **Reload** for this extension on `chrome://extensions`, then reload the VOS page. Chrome may ask you to allow access to the VOS app/API.

Chrome will show that this extension can access the seven ReadyMode sites and the VOS page. It requests no cookie, tab, storage, or broad all-sites permission.

For a dialer to work, this Chrome profile must already be signed in to that dialer. The extension reports dialers without a session instead of trying to log in or complete a security check. The call audio is uploaded to the authenticated VOS account that started the audit.

## Test

From the repository root run:

```sh
node --test browser-extension/ready-mode-client.test.cjs
```

Then, with the extension loaded and ReadyMode signed in, use **Find busiest dialer** to check sessions or start an audit. The audit uploads recordings to the VOS API and uses the existing analysis and saving flow.
