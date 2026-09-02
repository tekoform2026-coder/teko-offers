import io
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from PIL import Image

COLOR_PANEL = '#E8A5B2'      # Розов цвят за панели (TK)
COLOR_CORNER = '#96D28C'     # Зелен цвят за ъгли (EX / IN)
COLOR_CONCRETE = '#808588'   # Сиво за бетоновото ядро
COLOR_BORDER = '#222222'     # Тъмен кант


def _create_plotly_box(x, y, z, dx, dy, dz, color, name=""):
    """Създава 3D кутия за Plotly"""
    vx = [x, x+dx, x+dx, x, x, x+dx, x+dx, x]
    vy = [y, y, y+dy, y+dy, y, y, y+dy, y+dy]
    vz = [z, z, z, z, z+dz, z+dz, z+dz, z+dz]
    
    i = [0, 0, 4, 4, 0, 0, 2, 2, 0, 0, 1, 1]
    j = [1, 2, 6, 7, 5, 4, 7, 6, 7, 4, 6, 5]
    k = [2, 3, 5, 6, 1, 5, 3, 7, 3, 7, 2, 6]

    return go.Mesh3d(
        x=vx, y=vy, z=vz,
        i=i, j=j, k=k,
        color=color,
        flatshading=True,
        name=name,
        showscale=False
    )


def generate_wall_2d(element_data=None, *args, **kwargs):
    """Генерира 2D изображение"""
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_title("2D Развертка на Кофраж", fontsize=11, fontweight='bold')
    
    rect = plt.Rectangle((10, 10), 100, 20, facecolor=COLOR_PANEL, edgecolor=COLOR_BORDER, lw=1.5)
    ax.add_patch(rect)
    ax.text(60, 20, "TK ПАНЕЛ 120/270", color="black", ha="center", va="center", fontweight="bold")
    
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 40)
    ax.set_aspect('equal')
    ax.axis('off')
    
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)


def generate_wall_3d(element_structure=None, *args, **kwargs):
    """Генерира интерактивен Plotly 3D модел за st.plotly_chart()"""
    fig = go.Figure()

    if not element_structure or not isinstance(element_structure, list):
        element_structure = [
            {'type': 'panel', 'origin': (0, 0, 0), 'size': (100, 15, 270)},
            {'type': 'corner', 'origin': (-15, 0, 0), 'size': (15, 15, 270)},
            {'type': 'concrete', 'origin': (0, 15, 0), 'size': (100, 25, 270)}
        ]

    for block in element_structure:
        b_type = block.get('type', 'panel')
        x, y, z = block['origin']
        dx, dy, dz = block['size']

        color = COLOR_PANEL
        if b_type == 'corner':
            color = COLOR_CORNER
        elif b_type == 'concrete':
            color = COLOR_CONCRETE

        fig.add_trace(_create_plotly_box(x, y, z, dx, dy, dz, color, name=b_type))

    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0)
    )
    return fig


def generate_pdf_drawings(element_data=None, *args, **kwargs):
    """Генерира PDF файл с чертежи"""
    buffer = io.BytesIO()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_title("2D Развертка на Кофраж", fontsize=12, fontweight='bold')
    rect = plt.Rectangle((10, 10), 100, 20, facecolor=COLOR_PANEL, edgecolor=COLOR_BORDER, lw=1.5)
    ax.add_patch(rect)
    ax.text(60, 20, "TK ПАНЕЛ 120/270", color="black", ha="center", va="center", fontweight="bold")
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 40)
    ax.set_aspect('equal')
    ax.axis('off')
    
    plt.tight_layout()
    fig.savefig(buffer, format='pdf', bbox_inches='tight')
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()
