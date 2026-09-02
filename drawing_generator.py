import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

# Точни цветове според референтните PDF документи
COLOR_PANEL = '#E8A5B2'      # Розов цвят за панели (TK)
COLOR_CORNER = '#96D28C'     # Зелен цвят за ъгли (EX / IN)
COLOR_CONCRETE = '#808588'   # Сиво за бетоновото ядро
COLOR_WALER = '#7EC87E'      # Зелено за ригелите
COLOR_BORDER = '#222222'     # Тъмен кант за панелите
COLOR_GRID = '#E0E0E0'       # Светлосива мрежа на пода

def draw_3d_box(ax, origin, size, color, edgecolor=COLOR_BORDER, alpha=1.0):
    """Чертае 3D паралелепипед (панел, ъгъл или бетон)"""
    x, y, z = origin
    dx, dy, dz = size
    
    # 8-те върха на елемента
    vertices = np.array([
        [x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z],
        [x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]
    ])
    
    # 6-те стени
    faces = [
        [vertices[0], vertices[1], vertices[2], vertices[3]], # Долна
        [vertices[4], vertices[5], vertices[6], vertices[7]], # Горна
        [vertices[0], vertices[1], vertices[5], vertices[4]], # Предна
        [vertices[2], vertices[3], vertices[7], vertices[6]], # Задна
        [vertices[0], vertices[3], vertices[7], vertices[4]], # Лява
        [vertices[1], vertices[2], vertices[6], vertices[5]]  # Дясна
    ]
    
    poly = Poly3DCollection(faces, facecolors=color, edgecolors=edgecolor, linewidths=0.6, alpha=alpha)
    ax.add_collection3d(poly)

def draw_ground_grid(ax, bounds, step=50):
    """Чертае подложната сива мрежа (Grid) на пода"""
    min_x, max_x, min_y, max_y = bounds
    
    x_lines = np.arange(min_x - step, max_x + step*2, step)
    y_lines = np.arange(min_y - step, max_y + step*2, step)
    
    for x in x_lines:
        ax.plot([x, x], [y_lines[0], y_lines[-1]], [0, 0], color=COLOR_GRID, linewidth=0.8, zorder=1)
    for y in y_lines:
        ax.plot([x_lines[0], x_lines[-1]], [y, y], [0, 0], color=COLOR_GRID, linewidth=0.8, zorder=1)

def render_3d_element(ax, element_structure):
    """
    Основна функция за визуализация на 3D модела.
    element_structure съдържа списък от блокове: {'type': 'panel'|'corner'|'concrete', 'origin': (x,y,z), 'size': (dx,dy,dz)}
    """
    # 1. Настройка на перспективата и ортогоналния изглед
    ax.view_init(elev=25, azim=-60)
    ax.set_proj_type('ortho')
    ax.set_axis_off()  # Скриване на координатните оси
    
    all_x, all_y, all_z = [], [], []
    
    # 2. Чертаене на отделните компоненти
    for block in element_structure:
        b_type = block.get('type', 'panel')
        origin = block['origin']
        size = block['size']
        
        color = COLOR_PANEL
        if b_type == 'corner':
            color = COLOR_CORNER
        elif b_type == 'concrete':
            color = COLOR_CONCRETE
            
        draw_3d_box(ax, origin, size, color)
        
        all_x.extend([origin[0], origin[0] + size[0]])
        all_y.extend([origin[1], origin[1] + size[1]])
        all_z.extend([origin[2], origin[2] + size[2]])

    # 3. Чертаене на мрежата на пода
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    draw_ground_grid(ax, (min_x, max_x, min_y, max_y))

    # 4. Пропорционално мащабиране на осите
    max_range = np.array([max_x - min_x, max_y - min_y, max(all_z)]).max() / 2.0
    mid_x = (max_x + min_x) * 0.5
    mid_y = (max_y + min_y) * 0.5
    mid_z = max(all_z) * 0.5

    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(0, mid_z + max_range)
    ax.set_box_aspect([1, 1, 1])
