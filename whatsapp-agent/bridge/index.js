const { Client } = require('whatsapp-web.js');
const express    = require('express');
const qrcode     = require('qrcode-terminal');

const app  = express();
app.use(express.json());

const PORT             = 3001;
const INACTIVITY_LIMIT = 6 * 60 * 60 * 1000; // 6 hours in ms
const IDLE_CHECK_MS    = 60 * 1000;            // check every 60 seconds

let client       = null;
let isReady      = false;
let lastActivity = Date.now();
let qrShown      = false;

// ── Banner ────────────────────────────────────────────────────────────────────

console.log('\n╔══════════════════════════════════════════╗');
console.log('║    DRAGOO WHATSAPP BRIDGE  v1.0          ║');
console.log('║    Port: 3001  •  Auto-off: 6h idle      ║');
console.log('╚══════════════════════════════════════════╝\n');
console.log('Starting WhatsApp client — QR code will appear below...\n');

// ── WhatsApp Client ───────────────────────────────────────────────────────────

function initClient() {
    client = new Client({
        // No authStrategy = no session saved = fresh QR every start
        puppeteer: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        }
    });

    client.on('qr', (qr) => {
        console.log('━'.repeat(50));
        console.log('  📱  SCAN WITH WHATSAPP:');
        console.log('  WhatsApp → Settings → Linked Devices → Link a Device');
        console.log('━'.repeat(50) + '\n');
        qrcode.generate(qr, { small: true });
        console.log('\n' + '━'.repeat(50));
        qrShown = true;
    });

    client.on('loading_screen', (percent, message) => {
        process.stdout.write(`\r  ⏳ Loading ${percent}%  ${message}          `);
    });

    client.on('authenticated', () => {
        console.log('\n  ✓ Authenticated');
    });

    client.on('ready', () => {
        isReady      = true;
        lastActivity = Date.now();
        console.log('\n╔══════════════════════════════════════════╗');
        console.log('║  ✅  WHATSAPP CONNECTED — READY TO SEND  ║');
        console.log('║  ⏰  Auto-disconnect after 6h of idle     ║');
        console.log('╚══════════════════════════════════════════╝\n');
    });

    client.on('auth_failure', (msg) => {
        console.error('\n  ❌ Auth failed:', msg);
        isReady = false;
    });

    client.on('disconnected', (reason) => {
        console.log(`\n  🔌 Disconnected: ${reason}`);
        isReady = false;
    });

    client.initialize().catch(err => {
        console.error('  ❌ Init error:', err.message);
    });
}

// ── Inactivity watchdog ───────────────────────────────────────────────────────

setInterval(() => {
    if (!isReady) return;

    const idle      = Date.now() - lastActivity;
    const remaining = Math.round((INACTIVITY_LIMIT - idle) / 60000);

    if (idle >= INACTIVITY_LIMIT) {
        console.log('\n  ⏰ 6 hours of inactivity — disconnecting WhatsApp.');
        console.log('  Scan QR again to reconnect.\n');
        client.destroy();
        isReady = false;
    } else if (remaining % 60 === 0) {
        // log every hour
        console.log(`  ⏰ ${remaining} minutes until auto-disconnect`);
    }
}, IDLE_CHECK_MS);

// ── HTTP API ──────────────────────────────────────────────────────────────────

app.get('/status', (req, res) => {
    const idle_ms      = Date.now() - lastActivity;
    const idle_minutes = isReady ? Math.round(idle_ms / 60000) : null;
    const remaining    = isReady ? Math.max(0, Math.round((INACTIVITY_LIMIT - idle_ms) / 60000)) : null;
    res.json({
        connected:           isReady,
        idle_minutes:        idle_minutes,
        remaining_minutes:   remaining,
        qr_shown:            qrShown
    });
});

app.post('/send', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({
            error: 'WhatsApp not connected. Check the bridge window and scan the QR code.'
        });
    }

    const { phone, message } = req.body;
    if (!phone || !message) {
        return res.status(400).json({ error: 'phone and message fields are required' });
    }

    try {
        const chatId = phone.includes('@c.us') ? phone : `${phone}@c.us`;
        await client.sendMessage(chatId, message);
        lastActivity = Date.now();
        console.log(`  ✉  → ${phone}:  ${message.substring(0, 60)}${message.length > 60 ? '...' : ''}`);
        res.json({ success: true });
    } catch (err) {
        console.error('  ✗ Send error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
    console.log(`  Bridge API  →  http://localhost:${PORT}`);
    console.log(`  Status      →  http://localhost:${PORT}/status\n`);
    initClient();
});

// Cleanup on exit
process.on('SIGTERM', () => { if (client) client.destroy(); process.exit(0); });
process.on('SIGINT',  () => { if (client) client.destroy(); process.exit(0); });
