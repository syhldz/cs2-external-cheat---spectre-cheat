import sys
import time
import os
import math
import threading
import re
import ctypes
import json
import requests

# --------- Input / UI libs ---------
import keyboard
from pynput.mouse import Controller, Button

# --------- Win / Overlay / GL ---------
import pymem
import pymem.process
import win32gui
import win32con
import win32con as win32con2
import imgui
from imgui.integrations.glfw import GlfwRenderer
import glfw
import OpenGL.GL as gl

# --------- HTTP / UI ---------
import customtkinter as ctk

# ================== GLOBALS ==================
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

esp_rendering = 1
skeleton_enabled = False
line_esp_enabled = False

aimbot_enabled = False
aimbot_fov = 120
aimbot_smooth = 5
aimbot_key = "alt"

noflash_enabled = False
fov_enabled = False
fov_value = 110
default_fov = 90
hp_bar_enabled = True

# ================== OFFSETS (from dumper) ==================
dwEntityList = 0
dwLocalPlayerPawn = 0
dwViewMatrix = 0
dwCSGOInput = 0
dwLocalPlayerController = 0

m_iTeamNum = 0
m_fFlags = 0
m_lifeState = 0
m_pGameSceneNode = 0
m_modelState = 0
m_hPlayerPawn = 0
m_iHealth = 0
m_sSanitizedPlayerName = 0
m_flFlashDuration = 0
m_iDesiredFOV = 0
m_vecOrigin = 0

def get_offsets():
    """GitHub'dan en son offsetleri ve sınıf verilerini çeker."""
    global dwEntityList, dwLocalPlayerPawn, dwViewMatrix, dwCSGOInput, dwLocalPlayerController
    global m_iTeamNum, m_fFlags, m_lifeState, m_pGameSceneNode, m_modelState, m_hPlayerPawn, m_iHealth, m_sSanitizedPlayerName, m_flFlashDuration, m_iDesiredFOV, m_vecOrigin

    print("Offsets Uploading..")
    try:
        offsets_response = requests.get('https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json')
        offsets_response.raise_for_status()
        offsets = offsets_response.json()

        client_dll_dump_response = requests.get('https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json')
        client_dll_dump_response.raise_for_status()
        client_dll_dump = client_dll_dump_response.json()

        client_hpp_response = requests.get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.hpp")
        client_hpp_response.raise_for_status()
        client_hpp = client_hpp_response.text

        # offsets.json'dan global offsetleri al
        try:
            dwEntityList = offsets['client.dll']['dwEntityList']
            dwLocalPlayerPawn = offsets['client.dll']['dwLocalPlayerPawn']
            dwViewMatrix = offsets['client.dll']['dwViewMatrix']
            dwCSGOInput = offsets['client.dll']['dwCSGOInput']
            dwLocalPlayerController = offsets['client.dll']['dwLocalPlayerController']
        except KeyError as e:
            raise ValueError(f"Hata: offsets.json dosyasında beklenmeyen bir offset bulunamadı. Lütfen oyunun en son sürümünü kontrol edin. Eksik anahtar: {e}")

        # client_dll.json'dan sınıf offsetlerini al
        try:
            m_iTeamNum = client_dll_dump['client.dll']['classes']['C_BaseEntity']['fields']['m_iTeamNum']
            m_fFlags = client_dll_dump['client.dll']['classes']['C_BaseEntity']['fields']['m_fFlags']
            m_lifeState = client_dll_dump['client.dll']['classes']['C_BaseEntity']['fields']['m_lifeState']
            m_pGameSceneNode = client_dll_dump['client.dll']['classes']['C_BaseEntity']['fields']['m_pGameSceneNode']
            m_modelState = client_dll_dump['client.dll']['classes']['CSkeletonInstance']['fields']['m_modelState']
            m_hPlayerPawn = client_dll_dump['client.dll']['classes']['CCSPlayerController']['fields']['m_hPlayerPawn']
            m_iHealth = client_dll_dump['client.dll']['classes']['C_BaseEntity']['fields']['m_iHealth']
            m_sSanitizedPlayerName = client_dll_dump['client.dll']['classes']['CCSPlayerController']['fields']['m_sSanitizedPlayerName']
            m_flFlashDuration = client_dll_dump['client.dll']['classes']['C_CSPlayerPawnBase']['fields']['m_flFlashDuration']
            
            # m_vecOrigin'i dinamik olarak almayı dene başarısız olursa yedek kullan
            try:
                m_vecOrigin = client_dll_dump['client.dll']['classes']['C_BaseEntity']['fields']['m_vecOrigin']
            except KeyError:
                print("Uyarı: m_vecOrigin offseti bulunamadı. Sabit kodlanmış yedek kullanılıyor.")
                m_vecOrigin = 0x140 # En son doğrulanmış bir offset

        except KeyError as e:
            raise ValueError(f"Hata: client_dll.json dosyasında beklenmeyen bir sınıf offseti bulunamadı. Lütfen oyunun en son sürümünü kontrol edin. Eksik anahtar: {e}")

        m = re.search(r'm_iDesiredFOV\s*=\s*0x([0-9A-Fa-f]+)', client_hpp)
        if not m:
            raise ValueError("Hata: m_iDesiredFOV offseti bulunamadı!")
        m_iDesiredFOV = int(m.group(1), 16)

        print("Çektim")

    except requests.exceptions.RequestException as e:
        print(f"Hata: Offset dosyaları çekilirken bir ağ sorunu oluştu. Lütfen internet bağlantınızı kontrol edin veya GitHub deposunun erişilebilir olduğundan emin olun. Hata: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Hata: Offset değeri dump dosyasında bulunamadı. {e}")
        sys.exit(1)


print("Waiting for cs2.exe")
pm = None
client = None
while True:
    time.sleep(1)
    try:
        pm = pymem.Pymem("cs2.exe")
        client = pymem.process.module_from_name(pm.process_handle, "client.dll").lpBaseOfDll
        break
    except Exception:
        pass

get_offsets()

print("başlatıom")
os.system("cls")

# ================== HELPERS ==================
def w2s(mtx, posx, posy, posz, width, height):
    screenW = (mtx[12] * posx) + (mtx[13] * posy) + (mtx[14] * posz) + mtx[15]
    if screenW > 0.01:
        screenX = (mtx[0] * posx) + (mtx[1] * posy) + (mtx[2] * posz) + mtx[3]
        screenY = (mtx[4] * posx) + (mtx[5] * posy) + (mtx[6] * posz) + mtx[7]
        camX = width / 2
        camY = height / 2
        x = camX + (camX * screenX / screenW)
        y = camY - (camY * screenY / screenW)
        return [x, y]
    return [-999, -999]


def get_distance(pos1, pos2):
    return math.sqrt((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2 + (pos1[2]-pos2[2])**2)

# ================== AIMBOT ==================
def aimbot():
    global aimbot_enabled, aimbot_fov, aimbot_smooth, aimbot_key
    while True:
        time.sleep(0.001)
        if not aimbot_enabled or not keyboard.is_pressed(aimbot_key):
            continue
        try:
            local_player_pawn_addr = pm.read_longlong(client + dwLocalPlayerPawn)
            local_team = pm.read_int(local_player_pawn_addr + m_iTeamNum)
            local_origin_x = pm.read_float(local_player_pawn_addr + m_vecOrigin)
            local_origin_y = pm.read_float(local_player_pawn_addr + m_vecOrigin + 0x4)
            local_origin_z = pm.read_float(local_player_pawn_addr + m_vecOrigin + 0x8)
            local_origin = [local_origin_x, local_origin_y, local_origin_z]

        except Exception:
            continue

        view_matrix = [pm.read_float(client + dwViewMatrix + i * 4) for i in range(16)]
        best_dist = 99999
        target = None

        for i in range(64):
            try:
                entity = pm.read_longlong(client + dwEntityList)
                if not entity:
                    continue
                list_entry = pm.read_longlong(entity + ((8 * (i & 0x7FFF) >> 9) + 16))
                if not list_entry:
                    continue
                entity_controller = pm.read_longlong(list_entry + (120) * (i & 0x1FF))
                if not entity_controller:
                    continue
                entity_controller_pawn = pm.read_longlong(entity_controller + m_hPlayerPawn)
                if not entity_controller_pawn:
                    continue
                list_entry = pm.read_longlong(entity + (0x8 * ((entity_controller_pawn & 0x7FFF) >> 9) + 16))
                if not list_entry:
                    continue
                entity_pawn_addr = pm.read_longlong(list_entry + (120) * (entity_controller_pawn & 0x1FF))
                if not entity_pawn_addr or entity_pawn_addr == local_player_pawn_addr:
                    continue

                entity_alive = pm.read_int(entity_pawn_addr + m_lifeState)
                if entity_alive != 256:
                    continue
                entity_team = pm.read_int(entity_pawn_addr + m_iTeamNum)
                if entity_team == local_team:
                    continue

                game_scene = pm.read_longlong(entity_pawn_addr + m_pGameSceneNode)
                bone_matrix = pm.read_longlong(game_scene + m_modelState + 0x80)

                headX = pm.read_float(bone_matrix + 6 * 0x20)
                headY = pm.read_float(bone_matrix + 6 * 0x20 + 0x4)
                headZ = pm.read_float(bone_matrix + 5 * 0x20 + 0x8) + 8
                
                head_pos = w2s(view_matrix, headX, headY, headZ, WINDOW_WIDTH, WINDOW_HEIGHT)
                if head_pos[0] == -999:
                    continue

                dx = head_pos[0] - WINDOW_WIDTH / 2
                dy = head_pos[1] - WINDOW_HEIGHT / 2
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < aimbot_fov and dist < best_dist:
                    best_dist = dist
                    target = (dx, dy)
            except Exception:
                continue

        if target:
            move_x = int(target[0] / aimbot_smooth)
            move_y = int(target[1] / aimbot_smooth)
            win32gui.SetForegroundWindow(win32gui.GetForegroundWindow())
            import win32api
            win32api.mouse_event(win32con2.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)

def _draw_skeleton(entity_data, view_matrix, draw_list, local_player_origin):
    try:
        bone_matrix = entity_data['bone_matrix']
        
        points = {}
        def get_bone_pos(idx):
            return [
                pm.read_float(bone_matrix + idx * 0x20),
                pm.read_float(bone_matrix + idx * 0x20 + 0x4),
                pm.read_float(bone_matrix + idx * 0x20 + 0x8)
            ]


        head_pos = get_bone_pos(6)
        points['head'] = head_pos

        points['neck'] = get_bone_pos(5)

        points['chest'] = get_bone_pos(4)
        points['waist'] = get_bone_pos(0)


        points['l_knee'] = get_bone_pos(23)
        points['r_knee'] = get_bone_pos(26)
        points['l_foot'] = get_bone_pos(24)
        points['r_foot'] = get_bone_pos(27)

        points['l_shoulder'] = get_bone_pos(8)
        points['l_elbow']    = get_bone_pos(9)
        points['l_hand']     = get_bone_pos(10)
        points['r_shoulder'] = get_bone_pos(13)
        points['r_elbow']    = get_bone_pos(14)
        points['r_hand']     = get_bone_pos(15)

        def w2s_point(name):
            return w2s(view_matrix, *points[name], WINDOW_WIDTH, WINDOW_HEIGHT)
        screen = {k: w2s_point(k) for k in points}

        lines = [
            ('head','neck'), ('neck','chest'), ('chest','waist'),
            ('waist','l_knee'), ('waist','r_knee'),
            ('l_knee','l_foot'), ('r_knee','r_foot'),
            ('neck','l_shoulder'), ('l_shoulder','l_elbow'), ('l_elbow','l_hand'),
            ('neck','r_shoulder'), ('r_shoulder','r_elbow'), ('r_elbow','r_hand')
        ]

        for a,b in lines:
            if screen[a][0] != -999 and screen[b][0] != -999:
                draw_list.add_line(int(screen[a][0]), int(screen[a][1]),
                                   int(screen[b][0]), int(screen[b][1]),
                                   imgui.get_color_u32_rgba(1,1,0,1), 1.0)

        # Kafa için sabit boyutta bir daire çiz
        if screen['head'][0] != -999:
            head_radius = 3
            draw_list.add_circle_filled(int(screen['head'][0]), int(screen['head'][1]),
                                 head_radius, imgui.get_color_u32_rgba(1, 1, 0, 1),
                                 num_segments=16)
    except Exception:
        pass


# ================== ESP ==================
def esp(draw_list):
    global esp_rendering, aimbot_enabled, aimbot_fov, line_esp_enabled, hp_bar_enabled
    if esp_rendering == 0:
        return

    try:
        view_matrix = [pm.read_float(client + dwViewMatrix + i * 4) for i in range(16)]
        local_player_pawn_addr = pm.read_longlong(client + dwLocalPlayerPawn)
        local_team = pm.read_int(local_player_pawn_addr + m_iTeamNum)
        local_origin_x = pm.read_float(local_player_pawn_addr + m_vecOrigin)
        local_origin_y = pm.read_float(local_player_pawn_addr + m_vecOrigin + 0x4)
        local_origin_z = pm.read_float(local_player_pawn_addr + m_vecOrigin + 0x8)
        local_origin = [local_origin_x, local_origin_y, local_origin_z]
    except Exception:
        return

    players_to_render = []
    for i in range(64):
        try:
            entity = pm.read_longlong(client + dwEntityList)
            if not entity:
                continue
            list_entry = pm.read_longlong(entity + ((8 * (i & 0x7FFF) >> 9) + 16))
            if not list_entry:
                continue
            entity_controller = pm.read_longlong(list_entry + (120) * (i & 0x1FF))
            if not entity_controller:
                continue
            entity_controller_pawn = pm.read_longlong(entity_controller + m_hPlayerPawn)
            if not entity_controller_pawn:
                continue
            list_entry = pm.read_longlong(entity + (0x8 * ((entity_controller_pawn & 0x7FFF) >> 9) + 16))
            if not list_entry:
                continue
            entity_pawn_addr = pm.read_longlong(list_entry + (120) * (entity_controller_pawn & 0x1FF))
            if not entity_pawn_addr or entity_pawn_addr == local_player_pawn_addr:
                continue

            entity_alive = pm.read_int(entity_pawn_addr + m_lifeState)
            if entity_alive != 256:
                continue
            entity_team = pm.read_int(entity_pawn_addr + m_iTeamNum)
            if entity_team == local_team:
                continue

            health = pm.read_int(entity_pawn_addr + m_iHealth)
            if health <= 0:
                continue

            game_scene = pm.read_longlong(entity_pawn_addr + m_pGameSceneNode)
            bone_matrix = pm.read_longlong(game_scene + m_modelState + 0x80)
            head_pos3d = [
                pm.read_float(bone_matrix + 6 * 0x20),
                pm.read_float(bone_matrix + 6 * 0x20 + 0x4),
                pm.read_float(bone_matrix + 6 * 0x20 + 0x8) + 8
            ]
            feet_pos3d = [head_pos3d[0], head_pos3d[1], head_pos3d[2] - 72]
            
            players_to_render.append({
                'health': health,
                'head_pos3d': head_pos3d,
                'feet_pos3d': feet_pos3d,
                'bone_matrix': bone_matrix # İskelet için bone_matrix'i sakla
            })

        except Exception as e:
            print(f"Hata: ESP'de bir oyuncu işlenirken sorun oluştu: {e}")
            continue
            
    if not players_to_render:
        # print("Uyarı: ESP çizilecek oyuncu bulamıyor.")
        pass

    for player in players_to_render:
        try:
            head_screen = w2s(view_matrix, *player['head_pos3d'], WINDOW_WIDTH, WINDOW_HEIGHT)
            feet_screen = w2s(view_matrix, *player['feet_pos3d'], WINDOW_WIDTH, WINDOW_HEIGHT)
            if head_screen[0] == -999 or feet_screen[0] == -999:
                continue

            height = feet_screen[1] - head_screen[1]
            width = height / 2.2
            x1, y1 = int(head_screen[0] - width/2), int(head_screen[1])
            x2, y2 = int(head_screen[0] + width/2), int(feet_screen[1])
            draw_list.add_rect(x1, y1, x2, y2, imgui.get_color_u32_rgba(1, 0, 0, 1))

            if hp_bar_enabled:
                health = player['health']
                bar_height = y2 - y1
                bar_x = x1 - 6
                hp_height = int(bar_height * (health / 100))
                draw_list.add_rect_filled(bar_x, y2 - hp_height, bar_x+4, y2, imgui.get_color_u32_rgba(0, 1, 0, 1))
                draw_list.add_rect(bar_x, y1, bar_x+4, y2, imgui.get_color_u32_rgba(0, 0, 0, 1))

            if line_esp_enabled:
                try:

                    sx = WINDOW_WIDTH // 2
                    sy = WINDOW_HEIGHT
                    # Hedef: box'ın alt orta noktası + küçük offset (box'ın hemen altı)
                    tx = int((x1 + x2) // 2)
                    ty = int(y2 + 6)  # 6 piksel aşağıda; istersen arttırabilirsin
                    draw_list.add_line(sx, sy, tx, ty, imgui.get_color_u32_rgba(1, 0, 0, 1), thickness=1.5)
                except Exception:
                    pass

            if skeleton_enabled:
                _draw_skeleton(player, view_matrix, draw_list, local_origin)

        except Exception:
            continue

    if aimbot_enabled and aimbot_fov > 0:
        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        draw_list.add_circle(cx, cy, aimbot_fov, imgui.get_color_u32_rgba(1, 0, 0, 1), num_segments=100, thickness=1.5)

# ================== ESP THREAD (OpenGL ImGui overlay) ==================
def esp_thread():
    if not glfw.init():
        print("OpenGL context başlatılamadı.")
        return
    glfw.window_hint(glfw.TRANSPARENT_FRAMEBUFFER, glfw.TRUE)
    window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "ESP", None, None)
    hwnd = glfw.get_win32_window(window)
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME)
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
    ex_style = win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, -2, -2, 0, 0,
                          win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

    glfw.make_context_current(window)
    imgui.create_context()
    impl = GlfwRenderer(window)

    while not glfw.window_should_close(window):
        glfw.poll_events()
        impl.process_inputs()
        imgui.new_frame()
        imgui.set_next_window_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        imgui.set_next_window_position(0, 0)
        imgui.begin("overlay", flags=imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE |
                    imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_BACKGROUND)
        draw_list = imgui.get_window_draw_list()
        esp(draw_list)
        imgui.end()
        imgui.end_frame()
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        imgui.render()
        impl.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    impl.shutdown()
    glfw.terminate()

# ================== NOFLASH ==================
def noflash_thread():
    global noflash_enabled, dwLocalPlayerPawn, m_flFlashDuration
    while True:
        time.sleep(0.1)
        try:
            local_player_pawn = pm.read_longlong(client + dwLocalPlayerPawn)
            if local_player_pawn:
                if noflash_enabled:
                    pm.write_float(local_player_pawn + m_flFlashDuration, 0.0)
        except Exception:
            pass

# ================== FOV CHANGER ==================
def fov_thread():
    global fov_enabled, fov_value
    while True:
        time.sleep(0.1)
        try:
            local_controller = pm.read_longlong(client + dwLocalPlayerController)
            if not local_controller:
                continue
            if fov_enabled:
                pm.write_int(local_controller + m_iDesiredFOV, int(fov_value))
            else:
                pm.write_int(local_controller + m_iDesiredFOV, default_fov)
        except Exception:
            pass

# ================== CONFIG ==================
CONFIG_FILE = "config.json"

def save_config():
    config = {
        "aimbot_enabled": aimbot_enabled,
        "aimbot_fov": aimbot_fov,
        "aimbot_smooth": aimbot_smooth,
        "aimbot_key": aimbot_key,
        "esp_rendering": esp_rendering,
        "skeleton_enabled": skeleton_enabled,
        "line_esp_enabled": line_esp_enabled,  # kaydet
        "rect_width": rect_width,
        "rect_height": rect_height,
        "noflash_enabled": noflash_enabled,
        "fov_enabled": fov_enabled,
        "fov_value": fov_value,
        "hp_bar_enabled": hp_bar_enabled
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print("[Config] Ayarlar kaydedildi.")

def load_config():
    global aimbot_enabled, aimbot_fov, aimbot_smooth, aimbot_key
    global noflash_enabled, fov_enabled, fov_value, hp_bar_enabled

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        aimbot_enabled = config.get("aimbot_enabled", False)
        aimbot_fov = config.get("aimbot_fov", 120)
        aimbot_smooth = config.get("aimbot_smooth", 5)
        aimbot_key = config.get("aimbot_key", "alt")
        esp_rendering = config.get("esp_rendering", 1)
        skeleton_enabled = config.get("skeleton_enabled", False)
        line_esp_enabled = config.get("line_esp_enabled", False)
        rect_width = config.get("rect_width", 15)
        rect_height = config.get("rect_height", 15)
        noflash_enabled = config.get("noflash_enabled", False)
        fov_enabled = config.get("fov_enabled", False)
        fov_value = config.get("fov_value", 110)
        hp_bar_enabled = config.get("hp_bar_enabled", True)
        print("[Config] Ayarlar yüklendi.")
    except FileNotFoundError:
        print("[Config] config.json dosyası bulunamadı, varsayılan ayarlar kullanılıyor.")
    except Exception as e:
        print(f"[Config] Hata: {e}")

# ================== MENU (CustomTkinter) ==================
def menu_thread():
    global aimbot_enabled, aimbot_fov, aimbot_smooth, aimbot_key
    global esp_rendering, skeleton_enabled, line_esp_enabled
    global rect_width, rect_height
    global noflash_enabled
    global fov_enabled, fov_value
    global hp_bar_enabled

    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.title("SPECTRE CHEAT")
    app.geometry("720x560")
    app.resizable(False, False)
    app.configure(fg_color="#1a1a1a")

    # Font tanımları
    main_font = ctk.CTkFont(family="Inter", size=20, weight="bold")
    button_font = ctk.CTkFont(family="Inter", size=15, weight="bold")
    label_font = ctk.CTkFont(family="Inter", size=14)

    main_frame = ctk.CTkFrame(app, fg_color="transparent")
    main_frame.pack(fill="both", expand=True)

    sidebar = ctk.CTkFrame(main_frame, width=160, fg_color="#1f1f1f")
    sidebar.pack(side="left", fill="y", padx=(10, 0), pady=10)

    ctk.CTkLabel(sidebar, text="SPECTRE CHEAT", font=main_font, text_color="#c0392b").pack(pady=20)

    content = ctk.CTkFrame(main_frame, fg_color="#1f1f1f", corner_radius=10)
    content.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    frame_esp = ctk.CTkFrame(content, fg_color="transparent")
    frame_aim = ctk.CTkFrame(content, fg_color="transparent")
    frame_fov = ctk.CTkFrame(content, fg_color="transparent")
    frame_motion = ctk.CTkFrame(content, fg_color="transparent")
    frame_misc = ctk.CTkFrame(content, fg_color="transparent")
    frame_config = ctk.CTkFrame(content, fg_color="transparent")

    for f in (frame_esp, frame_aim, frame_motion, frame_fov, frame_misc, frame_config):
        f.place(relwidth=1, relheight=1)

    def show_frame(fr):
        fr.lift()

    ctk.CTkButton(sidebar, text="Aimbot", command=lambda: show_frame(frame_aim),
                  fg_color="#9c2727", hover_color="#c0392b", font=button_font).pack(pady=5, fill="x", padx=10)
    ctk.CTkButton(sidebar, text="Esp", command=lambda: show_frame(frame_esp),
                  fg_color="#9c2727", hover_color="#c0392b", font=button_font).pack(pady=5, fill="x", padx=10)
    ctk.CTkButton(sidebar, text="Fov Changer", command=lambda: show_frame(frame_fov),
                  fg_color="#9c2727", hover_color="#c0392b", font=button_font).pack(pady=5, fill="x", padx=10)
    ctk.CTkButton(sidebar, text="Misc", command=lambda: show_frame(frame_misc),
                  fg_color="#9c2727", hover_color="#c0392b", font=button_font).pack(pady=5, fill="x", padx=10)
    ctk.CTkButton(sidebar, text="Settings", command=lambda: show_frame(frame_config),
                  fg_color="#9c2727", hover_color="#c0392b", font=button_font).pack(pady=5, fill="x", padx=10)

    # ===== Aimbot UI =====
    ctk.CTkLabel(frame_aim, text="Aimbot Settings", font=main_font).pack(pady=(20, 10))
    def toggle_aim():
        global aimbot_enabled
        aimbot_enabled = not aimbot_enabled
        print(f"[Aimbot] {'Active' if aimbot_enabled else 'False'}")
    aim_check = ctk.CTkCheckBox(frame_aim, text="Aimbot", command=toggle_aim,
                                font=label_font, fg_color="#9c2727", hover_color="#c0392b", checkmark_color="#FFFFFF")
    aim_check.pack(pady=12)

    fov_slider_aim = ctk.CTkSlider(frame_aim, from_=0, to=500, number_of_steps=500,
                               command=lambda v: set_aim_fov(v), fg_color="#333333", progress_color="#c0392b", button_color="#c0392b", button_hover_color="#9c2727")
    fov_slider_aim.set(aimbot_fov); fov_slider_aim.pack(pady=6)
    fov_label_aim = ctk.CTkLabel(frame_aim, text=f"FOV: {aimbot_fov}°", font=label_font); fov_label_aim.pack()

    def set_aim_fov(v):
        global aimbot_fov
        aimbot_fov = int(float(v))
        fov_label_aim.configure(text=f"FOV: {aimbot_fov}°")

    smooth_slider = ctk.CTkSlider(frame_aim, from_=1, to=50, number_of_steps=49,
                                  command=lambda v: set_smooth(v), fg_color="#333333", progress_color="#c03927", button_color="#c0392b", button_hover_color="#c0392b")
    smooth_slider.set(aimbot_smooth); smooth_slider.pack(pady=6)
    smooth_label = ctk.CTkLabel(frame_aim, text=f"Smooth: {aimbot_smooth}", font=label_font); smooth_label.pack()
    def set_smooth(v):
        global aimbot_smooth
        aimbot_smooth = int(float(v))
        smooth_label.configure(text=f"Smooth: {aimbot_smooth}")

    ctk.CTkLabel(frame_aim, text="Aimbot key", font=label_font).pack(pady=(20, 5))
    aim_key_entry = ctk.CTkEntry(frame_aim, placeholder_text="key (alt, shift, mouse1)", font=label_font)
    aim_key_entry.pack(pady=6)
    aim_key_label = ctk.CTkLabel(frame_aim, text=f"Current key: {aimbot_key}", font=label_font)
    aim_key_label.pack()
    def save_aim_key():
        global aimbot_key
        new_key = aim_key_entry.get().strip().lower()
        if new_key:
            aimbot_key = new_key
            aim_key_label.configure(text=f"Mevcut Tuş: {aimbot_key}")
            print(f"[Aimbot] key assignment '{aimbot_key}' changed to.")
        else:
            print("[Aimbot] invalid key assignment.")
    ctk.CTkButton(frame_aim, text="Save Key", command=save_aim_key, font=label_font, fg_color="#9c2727", hover_color="#c0392b").pack(pady=6)

    # ===== Visuals (ESP) UI =====
    ctk.CTkLabel(frame_esp, text="ESP settings", font=main_font).pack(pady=(20, 10))
    def toggle_esp():
        global esp_rendering
        esp_rendering = 1 if esp_rendering == 0 else 0
        print(f"[ESP] {'Etkin' if esp_rendering else 'Devre Dışı'}")
    esp_check = ctk.CTkCheckBox(frame_esp, text="Box", command=toggle_esp,
                                font=label_font, fg_color="#9c2727", hover_color="#c0392b", checkmark_color="#FFFFFF")
    esp_check.select() if esp_rendering == 1 else esp_check.deselect()
    esp_check.pack(pady=12)

    def toggle_skeleton():
        global skeleton_enabled
        skeleton_enabled = not skeleton_enabled
        print(f"[İskelet] {'Etkin' if skeleton_enabled else 'Devre Dışı'}")
    skeleton_check = ctk.CTkCheckBox(frame_esp, text="Skeloton", command=toggle_skeleton,
                                     font=label_font, fg_color="#9c2727", hover_color="#c0392b", checkmark_color="#FFFFFF")
    skeleton_check.pack(pady=12)

    # ===== Line ESP checkbox =====
    def toggle_line_esp():
        global line_esp_enabled
        line_esp_enabled = not line_esp_enabled
        print(f"[Line ESP] {'Etkin' if line_esp_enabled else 'Devre Dışı'}")
    line_check = ctk.CTkCheckBox(frame_esp, text="Line", command=toggle_line_esp,
                                 font=label_font, fg_color="#9c2727", hover_color="#c0392b", checkmark_color="#FFFFFF")
    line_check.pack(pady=12)
    if line_esp_enabled:
        line_check.select()
    else:
        line_check.deselect()

    # ===== HP Bar checkbox (yeni) =====
    def toggle_hp_bar():
        global hp_bar_enabled
        hp_bar_enabled = not hp_bar_enabled
        print(f"[HP Bar] {'Etkin' if hp_bar_enabled else 'Devre Dışı'}")
    hp_check = ctk.CTkCheckBox(frame_esp, text="HP Bar", command=toggle_hp_bar,
                                font=label_font, fg_color="#9c2727", hover_color="#c0392b", checkmark_color="#FFFFFF")
    hp_check.pack(pady=12)
    if hp_bar_enabled:
        hp_check.select()
    else:
        hp_check.deselect()

    # ===== FOV Changer UI =====
    ctk.CTkLabel(frame_fov, text="FOV Settings", font=main_font).pack(pady=(20, 10))
    def toggle_fov():
        global fov_enabled
        fov_enabled = not fov_enabled
        print(f"[FOV] {'Etkin' if fov_enabled else 'Devre Dışı'}")
    fov_check = ctk.CTkCheckBox(frame_fov, text="FOV Changer", command=toggle_fov,
                                font=label_font, fg_color="#9c2727", hover_color="#c0392b", checkmark_color="#FFFFFF")
    fov_check.pack(pady=12)
    fov_slider = ctk.CTkSlider(frame_fov, from_=60, to=150, number_of_steps=90,
                               command=lambda v: set_fov(v), fg_color="#333333", progress_color="#c03927", button_color="#c0392b", button_hover_color="#c0392b")
    fov_slider.set(fov_value); fov_slider.pack(pady=6)
    fov_label = ctk.CTkLabel(frame_fov, text=f"FOV: {fov_value}", font=label_font); fov_label.pack()
    def set_fov(v):
        global fov_value
        fov_value = int(float(v))
        fov_label.configure(text=f"FOV: {fov_value}")

    # ===== Misc UI (NoFlash) =====
    ctk.CTkLabel(frame_misc, text="Misc", font=main_font).pack(pady=(2, 10))
    def toggle_noflash():
        global noflash_enabled
        noflash_enabled = not noflash_enabled
        print(f"[NoFlash] {'Etkin' if noflash_enabled else 'Devre Dışı'}")
    noflash_check = ctk.CTkCheckBox(frame_misc, text="NoFlash", command=toggle_noflash,
                                    font=label_font, fg_color="#9c2727", hover_color="#c0392b", checkmark_color="#FFFFFF")
    noflash_check.pack(pady=12)

    # ==========================

    # ===== Config UI =====
    ctk.CTkLabel(frame_config, text="Settings", font=main_font).pack(pady=(20, 10))
    ctk.CTkButton(frame_config, text="Config Save", command=save_config, font=label_font, fg_color="#9c2727", hover_color="#c0392b").pack(pady=12)
    ctk.CTkButton(frame_config, text="Config Upload", command=load_config, font=label_font, fg_color="#9c2727", hover_color="#c0392b").pack(pady=12)

    show_frame(frame_esp)
    app.mainloop()

if __name__ == "__main__":
    load_config()
    threading.Thread(target=esp_thread, daemon=True).start()
    threading.Thread(target=aimbot, daemon=True).start()
    threading.Thread(target=noflash_thread, daemon=True).start()
    threading.Thread(target=fov_thread, daemon=True).start()
    menu_thread()