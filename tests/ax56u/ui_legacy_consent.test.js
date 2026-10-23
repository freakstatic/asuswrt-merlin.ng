// Host-only regression tests. Run: node tests/ax56u/ui_legacy_consent.test.js
// No router, target executable, network access, or third-party packages needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const www = path.resolve(__dirname, '../../release/src/router/www');
const read = file => fs.readFileSync(path.join(www, file), 'utf8');
const scripts = file => [...read(file).matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]);
const tick = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

// A small DOM double: test event handlers and rendered notice contents, not layout.
function element() {
    return {
        style: {}, nodes: new Map(), listeners: {}, disabled: false, checked: false,
        innerHTML: '', textContent: '', parentNode: {style: {}},
        addEventListener(event, fn) { this.listeners[event] = fn; },
        querySelector(selector) {
            if (!this.nodes.has(selector)) this.nodes.set(selector, element());
            return this.nodes.get(selector);
        },
        appendChild(child) { this.child = child; }, append(child) { this.child = child; },
        attachShadow() { return this.shadowRoot = element(); }, remove() { this.removed = true; }
    };
}

function harness(model = 'RT-AX56U', consent = '0') {
    const requests = [], reads = [], alerts = [], timers = [], ui = new Map();
    const state = {productid: model, ASUS_EULA: consent, ASUS_EULA_time: '',
        ASUS_NEW_EULA: '1', ASUS_NEW_EULA_time: 'new-date', preferred_lang: 'EN',
        TM_EULA: '0', TM_EULA_time: '', link_internet: '2', asusddns_reg_result: 'unregister,200'};
    const controls = {fail: false, persist: true};
    const $ = selector => {
        if (!ui.has(selector)) ui.set(selector, {visible: true, hide() { this.visible = false; },
            show() { this.visible = true; }, toggle(v) { this.visible = v; },
            text(v) { this.value = v; }, attr() {}, remove() {},
            iphoneSwitch() { this.initialized = true; }});
        return ui.get(selector);
    };
    $.ajax = options => {
        requests.push(options);
        if (controls.fail) { if (options.error) options.error(); return; }
        if (options.url === '/set_ASUS_EULA.cgi' && controls.persist) state.ASUS_EULA = options.data.ASUS_EULA;
        let response = '';
        if (options.url === '/get_ASUS_privacy_policy.cgi') response = {ASUS_privacy_policy: '2', ASUS_privacy_policy_time: 'pp-date'};
        if (options.url === '/get_security_update.cgi') response = {security_update: '1'};
        if (options.success) options.success(response);
    };
    $.each = (items, fn) => items.forEach((item, i) => fn(i, item));
    const document = {createElement: element, body: element(), querySelector: () => element(),
        getElementById: () => element(), getElementsByTagName: () => [{src: '/js/httpApi.js'}]};
    const context = vm.createContext({console, document, $, alert: text => alerts.push(text),
        confirm: () => true, setTimeout: fn => timers.push(fn), clearTimeout() {},
        location: {reload() { context.reloads++; }}, reloads: 0,
        goTo: {Welcome() { context.welcomes++; }}, welcomes: 0,
        systemVariable: {}, window: {location: {pathname: '/QIS_wizard.htm'}}, top: {document}});
    vm.runInContext(read('js/httpApi.js'), context);
    context.httpApi.nvramGet = keys => {
        reads.push(keys);
        return Object.fromEntries(keys.map(key => [key, state[key]]));
    };
    context.httpApi.log = () => {};
    context.httpApi.hookGet = () => ({});
    vm.runInContext(read('js/asus_policy.js'), context);
    const evaluate = code => vm.runInContext(code, context);
    return {context, evaluate, state, requests, reads, controls, ui, timers, alerts,
        flush() { while (timers.length) timers.shift()(); },
        component(code = 'new PolicyModalComponent({policy:"PP"})') { return evaluate(code); }};
}

async function main() {
    // Factory defaults and upgrades use actual legacy consent, even when NEW_EULA
    // says the opposite, and do not invent PPv2 state or a legacy acceptance date.
    for (const consent of ['0', '1']) {
        const h = harness('RT-AX56U', consent);
        const status = await h.evaluate('PolicyStatus()');
        assert.equal(status.ASUS_EULA, consent);
        assert.equal(status.EULA_time, '');
        assert.equal(Object.hasOwn(status, 'PP'), false);
        assert.equal(Object.hasOwn(status, 'PP_time'), false);
        assert.equal(h.evaluate(`policyConsentRequired(${JSON.stringify(status)})`), consent !== '1');
        assert.equal(h.requests.length, 0);
        assert(!h.reads.flat().includes('ASUS_NEW_EULA'));
    }

    // All consent entry points render the baseline data-sharing disclosure.
    for (const code of ['new PolicyModalComponent({policy:"PP",securityUpdate:true,websUpdate:true})',
        'new PolicyModalComponent({policy:"EULA"})', 'new PolicyUpdateModalComponent({})',
        'new QisPolicyPageComponent({policy:"EULA"})', 'new QisPolicyPageComponent({policy:"PP"})']) {
        const h = harness(), modal = h.component(code), root = modal.render().shadowRoot;
        assert(root.innerHTML.includes('<#ASUS_eula_desc1_2_1#>')); // IP/MAC/serial/DDNS disclosure
        assert(!root.innerHTML.includes('<#ASUS_PP_'));
        assert(!root.querySelector('#legacy-age').checked);
        modal.accept();
        assert.equal(h.requests.length, 0); // age must be explicitly checked
        root.querySelector('#legacy-age').checked = true;
        modal.accept();
        assert.equal(h.requests.length, 1);
        assert.equal(h.requests[0].url, '/set_ASUS_EULA.cgi');
        assert.equal(h.requests[0].data.ASUS_EULA, '1');
        assert.equal(h.requests[0].dataType, undefined); // empty legacy response accepted
        assert.equal(h.state.ASUS_EULA, '1');
        assert.equal(h.state.ASUS_NEW_EULA, '1'); // no PPv2 writes
        assert(modal.render().removed);
        if (code.includes('Qis')) assert.equal(h.context.welcomes, 1);
    }

    // Decline is a genuine setup option: it progresses without silently signing.
    {
        const h = harness(), modal = h.component('new QisPolicyPageComponent({policy:"EULA"})');
        modal.render().shadowRoot.querySelector('.decline').listeners.click();
        assert.equal(h.context.welcomes, 1);
        assert.equal(h.state.ASUS_EULA, '0');
        assert.equal(h.requests.length, 0);
    }

    // Failed requests AND successful HTTP with no persisted consent must not run
    // service callbacks or advance setup. Buttons recover for a real retry.
    for (const failure of ['fail', 'persist']) {
        const h = harness();
        h.controls[failure] = failure === 'fail';
        const modal = h.component('new QisPolicyPageComponent({policy:"EULA"})');
        const root = modal.render().shadowRoot;
        root.querySelector('#legacy-age').checked = true;
        modal.accept();
        assert.equal(h.context.welcomes, 0);
        assert.equal(root.querySelector('.accept').disabled, false);
        assert(root.querySelector('.error').textContent.includes('retry'));
        h.controls.fail = false; h.controls.persist = true;
        modal.accept();
        assert.equal(h.context.welcomes, 1);
    }

    // Every ASUS-DDNS and account-service policy gate uses the legacy-aware
    // predicate. PPv2 is deliberately absent from legacy PolicyStatus().
    for (const file of ['Advanced_ASUSDDNS_Content.asp', 'Advanced_Smart_Home_Alexa.asp',
        'Advanced_Smart_Home_IFTTT.asp', 'Advanced_TencentDownloadAcceleration.asp',
        'Advanced_FirmwareUpgrade_Content.asp']) {
        assert(!/if\s*\(data\.PP == 0/.test(read(file)), file);
        assert(read(file).includes('policyConsentRequired(data)'), file);
    }
    // Exercise the actual DDNS apply caller, not a reimplementation of its gate.
    for (const signed of ['0', '1']) {
        const h = harness('RT-AX56U', signed);
        h.context.document.form = {ddns_enable_x: {value: '1'}, ddns_server_x: {value: 'WWW.ASUS.COM'}};
        h.context.applied = 0;
        h.context.applyRule = () => h.context.applied++;
        h.evaluate(read('Advanced_ASUSDDNS_Content.asp').match(/function apply_eula_check\(\)\{[\s\S]*?\n\}/)[0]);
        h.evaluate('apply_eula_check()'); await tick();
        if (signed === '0') {
            assert.equal(h.context.applied, 0);
            const root = h.context.top.document.body.child.shadowRoot;
            root.querySelector('#legacy-age').checked = true;
            root.querySelector('.accept').listeners.click();
        }
        assert.equal(h.context.applied, 1);
        assert(h.requests.every(r => r.url === '/set_ASUS_EULA.cgi'));
    }

    // Retained QIS routes handle preserved consent with no timestamp without PP.
    for (const consent of ['0', '1']) {
        const h = harness('RT-AX56U', consent);
        h.evaluate(read('sysdep/FUNCTION/QIS_V3/mobile/js/handler.js').split('goTo.EULA = function(){')[1].split('goTo.WANOption =')[0].replace(/^/, 'goTo.EULA = function(){'));
        h.evaluate('goTo.EULA()'); await tick();
        assert.equal(h.context.welcomes, consent === '1' ? 1 : 0);
        assert.equal(h.requests.length, 0);
        if (consent === '1') { h.evaluate('goTo.PP()'); await tick(); assert.equal(h.context.welcomes, 2); }
    }

    // Withdrawal follows the baseline unregister -> poll -> legacy setter
    // ordering; local consent must be read back, not fabricated from HTTP 200.
    for (const result of ['unregister,200', 'unregister,390', '']) {
        const h = harness('RT-AX56U', '1'); h.state.asusddns_reg_result = result;
        let done = false, unconfirmed;
        h.context.httpApi.legacyAsusConsent.withdraw((state, warning) => { done = true; unconfirmed = warning; }, () => assert.fail('withdraw failed'));
        h.flush();
        assert(done);
        assert.equal(unconfirmed, result !== 'unregister,200');
        assert.deepEqual(h.requests.map(r => r.url), ['/unreg_ASUSDDNS.cgi', '/set_ASUS_EULA.cgi']);
        assert.equal(h.state.ASUS_EULA, '0');
    }
    {
        const h = harness('RT-AX56U', '1'); h.controls.persist = false;
        let success = false, error = false;
        h.context.httpApi.legacyAsusConsent.withdraw(() => success = true, () => error = true);
        assert(!success && error);
        assert.equal(h.state.ASUS_EULA, '1');
        h.controls.fail = true; error = false;
        h.context.httpApi.legacyAsusConsent.withdraw(() => assert.fail(), () => error = true);
        assert(error);
    }
    {
        const h = harness('RT-AX56U', '1');
        h.context.withdrawn = 0;
        const modal = h.component('new PolicyWithdrawModalComponent({policy:"PP", knowRiskCallback:()=>withdrawn++})');
        modal.render().shadowRoot.querySelector('.decline').listeners.click();
        assert.equal(h.context.withdrawn, 0); assert.equal(h.requests.length, 0);
        const confirm = h.component('new PolicyWithdrawModalComponent({policy:"PP", knowRiskCallback:()=>withdrawn++})');
        confirm.accept();
        assert.equal(h.state.ASUS_EULA, '0'); assert.equal(h.context.withdrawn, 1);
        assert.equal(h.requests[0].url, '/unreg_ASUSDDNS.cgi');
    }
    {
        const h = harness('RT-AX56U', '1'); h.state.link_internet = '0';
        let error = false;
        h.context.httpApi.legacyAsusConsent.withdraw(() => assert.fail(), () => error = true);
        assert(error); assert.equal(h.state.ASUS_EULA, '1'); assert.equal(h.requests.length, 0);
        // A previous asynchronous NVRAM retry must not survive a fresh read.
        h.evaluate('asyncData.get.ASUS_EULA = "0"; httpApi.legacyAsusConsent.get()');
        assert.equal(h.evaluate('Object.hasOwn(asyncData.get, "ASUS_EULA")'), false);
    }
    // Privacy page exposes actual state and the legacy withdrawal, hides PPv2.
    for (const consent of ['0', '1']) {
        const h = harness('RT-AX56U', consent);
        h.context.show_menu = () => {}; h.context.ui_lang = 'EN';
        h.context.setTimeout = () => {};
        scripts('Advanced_Privacy.asp').forEach(code => h.evaluate(code));
        h.evaluate('initial()');
        assert.equal(h.ui.get('#eula, #pp').visible, false);
        assert.equal(h.ui.get('#asus_withdraw_btn').visible, consent === '1');
        assert.equal(h.ui.get('#legacy_consent_status').value, 'ASUS_EULA=' + consent);
        if (consent === '1') { h.evaluate('withdraw_eula("asus")'); assert.equal(h.state.ASUS_EULA, '0'); assert.equal(h.context.reloads, 1); }
        assert(!h.requests.some(r => /privacy_policy|NEW_EULA/.test(r.url)));
    }

    // Unsupported table is hidden including initialization: no API request at
    // all on AX56U, whereas other models retain the original switch/getter.
    const securityScript = scripts('Advanced_FirmwareUpgrade_Content.asp').find(s => s.includes("iphoneSwitch(httpApi.securityUpdate.get()"));
    for (const model of ['RT-AX56U', 'RT-AX58U']) {
        const h = harness(model); await tick(); h.requests.length = 0;
        h.evaluate(securityScript);
        assert.equal(h.ui.get('#secur_stab_setting').visible, model !== 'RT-AX56U');
        assert.equal(h.requests.length, model === 'RT-AX56U' ? 0 : 1);
    }
    {
        const h = harness();
        h.context.httpApi.newEula.set('1', () => assert.fail());
        h.context.httpApi.privateEula.set('1', () => assert.fail());
        await assert.rejects(h.context.httpApi.privateEula.get(), /unsupported/);
        await assert.rejects(h.context.httpApi.newEula.get(), /unsupported/);
        h.context.httpApi.securityUpdate.get(); h.context.httpApi.securityUpdate.set(1);
        assert.equal(h.requests.length, 0);
        h.evaluate('function checkPolicy() {' + read('state.js').split('function checkPolicy() {')[1].split('\nif (')[0]);
        h.evaluate('checkPolicy()'); await tick();
        assert.equal(h.requests.length, 0);
    }
    {
        const h = harness('RT-AX58U');
        const state = await h.evaluate('PolicyStatus()');
        assert.equal(state.PP, '2'); assert.equal(state.PP_time, 'pp-date');
        assert.equal(state.EULA, '1'); assert.equal(state.legacy, undefined);
        h.context.httpApi.newEula.set('1'); h.context.httpApi.privateEula.set('1');
        assert(h.requests.some(r => r.url === '/set_ASUS_NEW_EULA.cgi'));
        assert(h.requests.some(r => r.url === '/set_ASUS_privacy_policy.cgi'));
    }

    // Parse changed UI scripts after removing HTTPD template expressions. This
    // catches accidental syntax errors without executing any firmware binary.
    for (const file of ['Advanced_Privacy.asp', 'Advanced_ASUSDDNS_Content.asp',
        'Advanced_Smart_Home_Alexa.asp', 'Advanced_Smart_Home_IFTTT.asp',
        'Advanced_TencentDownloadAcceleration.asp', 'Advanced_FirmwareUpgrade_Content.asp',
        'sysdep/FUNCTION/QIS_V3/QIS_wizard.htm']) {
        for (const code of scripts(file)) new vm.Script(code.replace(/<%[\s\S]*?%>/g, '0'));
    }
    for (const file of ['state.js', 'sysdep/FUNCTION/QIS_V3/mobile/js/handler.js']) {
        new vm.Script(read(file).replace(/<%[\s\S]*?%>/g, '0'));
    }
    // Dictionary values can contain unescaped apostrophes (notably French).
    // Validate the added localized component after actual HTTPD-style expansion.
    const dictionaries = fs.readdirSync(www).filter(file => file.endsWith('.dict'));
    assert(dictionaries.length > 0, 'No dictionaries found; include www/*.dict in a sparse checkout');
    for (const file of dictionaries) {
        const dict = Object.fromEntries(read(file).split(/\r?\n/).filter(line => line.includes('=')).map(line => {
            const pos = line.indexOf('='); return [line.slice(0, pos), line.slice(pos + 1)];
        }));
        const component = read('js/asus_policy.js').split('class LegacyAsusPolicyComponent {')[1].split('\nclass PolicyScrollDiv')[0];
        new vm.Script(('class LegacyAsusPolicyComponent {' + component).replace(/<#([^#]+)#>/g, (token, key) => dict[key] || token), {filename: file});
    }
    console.log('PASS: legacy consent, QIS, DDNS, withdrawal, unsupported security UI, other-model parity, and JS syntax');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
