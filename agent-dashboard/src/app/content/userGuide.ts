// All user-facing help text for the dashboard lives here, so the wording can
// be edited without touching any component. The same panel entries feed both
// the per-panel info popovers and the User Guide dialog.

export interface PanelGuide {
  title: string;
  what: string;
  how?: string;
  action?: string;
}

export type PanelGuideId =
  | 'identity'
  | 'mockMode'
  | 'protection'
  | 'relay'
  | 'lastThreat'
  | 'cpu'
  | 'ram'
  | 'throughput'
  | 'detectionLog'
  | 'blacklist';

export const PANEL_GUIDES: Record<PanelGuideId, PanelGuide> = {
  identity: {
    title: 'Header IP / MAC',
    what: "This computer's own network address (IP) and hardware address (MAC).",
    how: 'The first value is the IP address, the second is the MAC address. A dash means it is not known yet.',
  },
  mockMode: {
    title: 'MOCK MODE badge',
    what: 'The SentiNet background service (tray app / daemon) is not detected, so the dashboard cannot show live data.',
    how: 'While this badge is blinking, the numbers on screen are simulated, not real.',
    action: 'Start SentiNet with the launch script. The badge disappears once the service is running.',
  },
  protection: {
    title: 'Protection Status',
    what: 'Shows whether SentiNet is actively protecting this computer.',
    how: 'PROTECTED means SentiNet is capturing and checking ARP traffic and blocking attackers. UNPROTECTED means it is idle. The Turn ON/OFF button only appears when the service is running.',
    action: 'Keep it PROTECTED while you are on shared Wi-Fi. Turning OFF also disconnects this device from the relay.',
  },
  relay: {
    title: 'Relay Connection',
    what: 'Shows whether this device is connected to the SentiNet relay.',
    how: 'ONLINE means this device can share and receive threat alerts with other users (Tier 3 Bayanihan). OFFLINE means it still protects itself locally but will not receive other users\' alerts. "Network" shows the Wi-Fi or connection name.',
    action: 'If it stays OFFLINE, make sure Protection is ON and see Troubleshooting in the User Guide.',
  },
  lastThreat: {
    title: 'Last Detected Threat',
    what: 'The most recent threat SentiNet blocked.',
    how: "Shows the time, the attack type and the attacker's MAC address. NONE DETECTED means nothing has been blocked yet.",
    action: 'Nothing — the attacker is already blocked. The Detection Log below shows the full history.',
  },
  cpu: {
    title: 'CPU Load',
    what: 'How much CPU the SentiNet service itself uses (not the whole computer).',
    how: 'Low values are expected; it shows SentiNet is lightweight.',
  },
  ram: {
    title: 'System RAM Usage',
    what: 'Memory use of the computer and of SentiNet.',
    how: 'The ring is total memory used by the whole computer. "SentiNet: X MB" is the memory used by SentiNet itself.',
  },
  throughput: {
    title: 'Traffic Throughput',
    what: 'Running totals of ARP packets since protection was turned on.',
    how: 'INSPECTED = ARP packets checked. DROPPED = packets from blacklisted attackers that were blocked. PASSED = packets that were allowed through to the ML check.',
    action: 'Nothing. SentiNet only inspects ARP packets, so on a quiet network these numbers can stay at 0 — that is normal.',
  },
  detectionLog: {
    title: 'Detection Log',
    what: 'A list of recent detections.',
    how: 'Tier 2 = caught by the Machine Learning model on this device. Tier 1 = an attacker already on the blacklist was blocked again. Tier 3 = blocked because another SentiNet user reported it through the relay.',
  },
  blacklist: {
    title: 'Tier-1 Blacklist',
    what: 'The MAC addresses that are currently blocked.',
    how: 'Origin "Local" = detected by this device. "From Relay" = learned from another user (proof the collaborative defense works).',
    action: 'Nothing. Your own device and your gateway/router are never blacklisted.',
  },
};

// Order the panels appear in the guide (matches the dashboard, top to bottom).
export const PANEL_GUIDE_ORDER: PanelGuideId[] = [
  'identity',
  'mockMode',
  'protection',
  'relay',
  'lastThreat',
  'cpu',
  'ram',
  'throughput',
  'detectionLog',
  'blacklist',
];

export const POPOVER_LABELS = {
  what: 'What is this?',
  how: 'How to read it',
  action: 'What should I do?',
};

export const GUIDE_TITLE = 'SentiNet User Guide';
export const GUIDE_BUTTON_LABEL = 'User Guide';
export const FIRST_VISIT_HINT = 'New here? Open the User Guide';

export const GUIDE_INTRO = {
  heading: 'What is SentiNet?',
  body:
    'SentiNet protects this laptop from ARP spoofing / man-in-the-middle attacks on shared Wi-Fi, ' +
    'where someone on the same network tries to secretly route your traffic through their device. ' +
    'It works in three tiers: Tier 1 is a Fast-Filter blacklist that instantly blocks known attackers, ' +
    'Tier 2 is Machine Learning detection that spots new attacks, and Tier 3 is Bayanihan ' +
    'collaborative sharing, where SentiNet users warn each other through the relay.',
};

export const GETTING_STARTED = {
  heading: 'Getting started',
  steps: [
    'Start SentiNet with the launch script.',
    'Click the tray icon and turn Protection ON (or use the button on the dashboard).',
    'Check that Relay Connection shows ONLINE.',
    'Leave it running. SentiNet works in the background while you use the Wi-Fi.',
  ],
};

export const PANELS_HEADING = 'Panel by panel';

export const STATUS_COLORS = {
  heading: 'Status colors',
  items: [
    { color: '#00aa55', label: 'Green', meaning: 'Protected / online / passed.' },
    { color: '#c0392b', label: 'Red', meaning: 'Dropped / blocked / turn off.' },
    { color: '#3a5070', label: 'Gray-blue', meaning: 'Unprotected / offline.' },
    { color: '#f59e0b', label: 'Amber, blinking "MOCK MODE"', meaning: 'The background service is not running.' },
  ],
};

export const TROUBLESHOOTING = {
  heading: 'Troubleshooting',
  symptomLabel: 'Symptom',
  fixLabel: 'What to do',
  rows: [
    {
      symptom: 'MOCK MODE is showing',
      fix: 'The tray app/daemon is not running. Run the start script (as Administrator on Windows / with sudo on Mac/Linux).',
    },
    {
      symptom: 'Counters stuck at 0',
      fix: 'There is no ARP traffic on the network yet. This is normal on a quiet network.',
    },
    {
      symptom: 'Relay OFFLINE',
      fix: "Check the relay's IP address, that the relay is running, and that port 8771 is not blocked by a firewall. Also make sure Protection is ON.",
    },
    {
      symptom: 'Toggle button missing',
      fix: 'The service is not running (MOCK MODE). Start it with the launch script.',
    },
    {
      symptom: 'My router/gateway got blocked?',
      fix: 'It cannot. SentiNet never blocks this device or its gateway.',
    },
  ],
};

export const GLOSSARY = {
  heading: 'Glossary',
  terms: [
    { term: 'ARP', definition: 'Address Resolution Protocol. How devices on a local network find out which hardware (MAC) address belongs to an IP address.' },
    { term: 'ARP spoofing', definition: 'An attack where a device sends fake ARP messages to pretend it is another device, usually the router, so your traffic is sent to the attacker.' },
    { term: 'MAC address', definition: "A device's hardware address on the network, written like aa:bb:cc:dd:ee:ff." },
    { term: 'MITM', definition: 'Man-in-the-middle. An attacker secretly sits between you and the internet and can read or change your traffic.' },
    { term: 'Relay node', definition: 'The SentiNet server that passes threat alerts between SentiNet users.' },
    { term: 'Blacklist', definition: 'The list of MAC addresses SentiNet is currently blocking.' },
    { term: 'Tier 1', definition: 'Fast-Filter. Instantly blocks packets from attackers already on the blacklist.' },
    { term: 'Tier 2', definition: 'Machine Learning detection on this device. Catches attackers that are not on the blacklist yet.' },
    { term: 'Tier 3', definition: 'Collaborative sharing. Blocks attackers reported by other SentiNet users through the relay.' },
    { term: 'Bayanihan', definition: 'A Filipino word for community members helping each other. In SentiNet it means users protect one another by sharing threat alerts.' },
  ],
};
