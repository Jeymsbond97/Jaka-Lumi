# 02. Network and access

How to get a computer onto the Lumi network, which addresses and ports exist, and which web pages and apps to use. **Passwords are not in this file**: they are in [private/ACCESS.md](private/ACCESS.md) (local only, not on GitHub).

---

## 1. Network map

```
                         Lumi internal network 192.168.10.0/24
   ┌──────────────────────────────────────────────────────────────────────────┐
   │  192.168.10.90   robot controller (MiniCab):                              │
   │                  - arm SDK (jkrc)                                         │
   │                  - Cobo π web UI          https://192.168.10.90           │
   │                  - body API + web UI      http://192.168.10.90:5000       │
   │  192.168.10.10   AGV base computer:                                       │
   │                  - AGV TCP API            192.168.10.10:31001             │
   │                  - monitor / mapping UI   http://192.168.10.10:9001       │
   │                  - map builder            http://192.168.10.10:8809       │
   │  192.168.10.79   internal Wi-Fi router (Cudy WR1200E, access point)       │
   │  192.168.10.9    gateway (as shown on the router page)                    │
   └──────────────────────────────────────────────────────────────────────────┘
        ▲ Wi-Fi "Lumi<serial>" (2.4 GHz and -5G)        ▲ RJ45 on the back of the base
        │                                               │
   laptop / Jetson Thor (192.168.10.x) ─────────────────┘
   + USB 3.0 cable to the base for the head/torso cameras and the microphone array
```

| Service | Address | Login | Notes |
|---|---|---|---|
| Arm SDK (`jkrc`) | `192.168.10.90` | — | Used by every vendor demo and the ROS arm server |
| Cobo π (arm web app) | `https://192.168.10.90` (also `http://`) | Administrator, see ACCESS.md | Accept the self-signed certificate. Settings, manual jog, external axes, programs |
| Body (lift/waist/head) web UI | `http://192.168.10.90:5000` | none | ExtAxis page: Enable / Disable / Reset / Stop, joint table, chart, Upgrade page |
| Body HTTP API | `http://192.168.10.90:5000/api/extaxis/...` | none | [03_BODY_LIFT_WAIST_HEAD.md](03_BODY_LIFT_WAIST_HEAD.md) |
| AGV TCP API | `192.168.10.10:31001` | none | [05_AGV_BASE.md](05_AGV_BASE.md) |
| AGV monitor and mapping | `http://192.168.10.10:9001` | none | Chrome recommended. Map builder pops up on port 8809 |
| Robot Wi-Fi router admin | `http://192.168.10.79` | see ACCESS.md | Cudy WR1200E in access-point mode |
| MiniCab LAN1 (fixed) | `10.5.5.x` (controller at `10.5.5.100` in old docs) | — | Old LumiAPI doc and the VR-teleop defaults use `10.5.5.100` |
| AGV chassis Wi-Fi (alternative) | SSID `admin_xxxxxx` | see ACCESS.md | From the chassis manual; may not exist on Lumi, which has its own router |
| VR teleop receiver (vendor) | PC port 8018 (docs) / 9852 (launch file) | — | [09_ROS2_TELEOP_AND_SIM.md](09_ROS2_TELEOP_AND_SIM.md) |

Ports summary: `5000` body HTTP, `443/80` Cobo π, `31001` AGV TCP, `9001` AGV web, `8809` AGV map builder, `22` SSH on the Jetson, `8000`/`8080`/`5173` voice-assistant services on the Jetson ([08](08_NVIDIA_THOR.md)).

---

## 2. Connect a computer

### Option A: Wi-Fi

1. Read the serial on the robot's name plate.
2. Join the Wi-Fi `Lumi<serial>` (our robot: see ACCESS.md; there is a 2.4 GHz and a `-5G` network). Password: factory default in ACCESS.md.
3. Check your IP address. It must be `192.168.10.x`. If it is `10.5.5.x`, follow "Fix a 10.5.5.x address" below.
4. Test: `ping 192.168.10.90` and `ping 192.168.10.10`, then open `http://192.168.10.90:5000` in a browser.

### Option B: cable

1. Connect your computer to the gigabit RJ45 port on the back of the base.
2. If no address is given by DHCP, set a static address (below), for example `192.168.10.150/24`.
3. Test as above.

For cameras and the microphone, also plug a USB 3.0 cable from the computer into the base's USB 3.0 port (the one for "head/torso cameras and voice module").

### Fix a 10.5.5.x address

When the laptop receives `10.5.5.xxx` (gateway `10.5.5.1`) from the robot Wi-Fi, the robot services do not answer (company Notion "Lumi service access info", `private/images/access-01-wifi-10-5-5-problem.png`). Set the address by hand:

| Field | Value |
|---|---|
| IP address | a free `192.168.10.x`, e.g. `192.168.10.150` (avoid .9, .10, .79, .90 and addresses already in use) |
| Subnet mask | `255.255.255.0` |
| Gateway | `192.168.10.9` (gateway shown on the robot router) |
| DNS | `192.168.10.9` or leave empty |

**Windows 10/11:** Settings → Network & Internet → Wi-Fi (or Ethernet) → the connection → IP assignment → Edit → Manual → IPv4 on → enter the values → Save. Or: Control Panel → Network and Sharing Center → Change adapter settings → right-click the adapter → Properties → Internet Protocol Version 4 → Use the following IP address.

**macOS:** System Settings → Wi-Fi (or Ethernet) → Details… next to the network → TCP/IP → Configure IPv4: *Manually* → enter IP, mask, router → OK.

**Ubuntu:** Settings → Network → gear icon → IPv4 → Manual → address, netmask, gateway → Apply; or `nmcli con mod "<name>" ipv4.method manual ipv4.addresses 192.168.10.150/24 ipv4.gateway 192.168.10.9 && nmcli con up "<name>"`.

Before choosing an address, check it is free: `ping 192.168.10.150` should not answer.

### Keep internet while on the robot network

The vendor demo PC used the cable for the robot and Wi-Fi for the internet (needed for cloud LLM APIs). On Linux:

```bash
# 192.168.10.* over the wired port, everything else over Wi-Fi
sudo ip route replace 192.168.10.0/24 via 192.168.10.1 dev <wired-iface> metric 50
sudo ip route replace default via <wifi-gateway> dev <wifi-iface> metric 100
sudo ip route del default via 192.168.10.1 dev <wired-iface> 2>/dev/null
```

On macOS: System Settings → Network → "…" → Set Service Order, put Wi-Fi above Ethernet; macOS still reaches `192.168.10.x` through the cable because it is on that subnet.

---

## 3. Apps and tools

| Tool | What for | Where to get it | Platform |
|---|---|---|---|
| Browser (Chrome) | Cobo π, body web UI, AGV web UI | — | any |
| JAKA App (Zu App) v1.7.2 | Arm setup, safety, payload, programs (older UI) | https://www.jaka.com/download (iOS: App Store "JAKA App"; Android; Windows) | Windows / Android / iOS |
| Cobo π | Newer arm UI; served by the controller (≥ 1.7.1) or installed (Windows PC / Android) | Browser to the robot IP, or installer from JAKA | any browser |
| JAKA SDK v2.2.7 | Python / C++ arm control | [zip](https://www.jaka.com/prod-api/common/download/resource?resource=%2Fprofile%2Fupload%2F2025%2F04%2F25%2F20250425134342A024.zip); also inside the JAKA_Lumi repo | Linux x86_64 / aarch64, Windows (no macOS) |
| OrbbecViewer / Orbbec SDK v1.10.8 | Check and tune the cameras | https://github.com/orbbec/OrbbecSDK/releases (Windows exe, Linux amd64/arm64 deb, macOS arm64 viewer zip) | all |
| pyorbbecsdk | Python camera access | https://github.com/orbbec/pyorbbecsdk | Linux, Windows (macOS: verify) |
| SSH client (Terminal, MobaXterm on Windows) | Log into the Jetson Thor | — | any |
| VS Code / Cursor + Docker extension | Develop inside the Jetson containers | — | any |
| PICO Developer Center | Install the VR teleop app | https://developer-cn.picoxr.com/resources/#pdc | Windows / macOS |

The JAKA App manual's recommended tablet note: Android 10–13, Snapdragon 835-class; disable battery saving for the app so the robot does not disconnect when the screen locks.

Cobo π browser requirements: Windows 10 64-bit + Chrome ≥ 110, or Android 13 tablet; Cobo π service package needs controller ≥ 1.7.1 (otherwise upload it through the Zu App: Settings → Version upgrade).

---

## 4. Checklist: is everything reachable?

```bash
ping -c 2 192.168.10.90                 # robot controller
ping -c 2 192.168.10.10                 # AGV computer
curl -s http://192.168.10.90:5000/api/extaxis/status     # body joints JSON
curl -s http://192.168.10.90:5000/api/extaxis/sysinfo    # body firmware info
python3 - <<'EOF'
import socket, json
s = socket.create_connection(("192.168.10.10", 31001), timeout=3)
s.sendall(b"/api/robot_status")
print(json.loads(s.recv(65536)))
EOF
```

Open in the browser: `https://192.168.10.90` (Cobo π), `http://192.168.10.90:5000` (body), `http://192.168.10.10:9001` (AGV).
