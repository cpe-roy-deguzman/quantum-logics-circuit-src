import sys
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

WIN_WIDTH = 1280
WIN_HEIGHT = 720

TYPE_QUBIT = 0
TYPE_GATE = 1

class CircuitComponent(QGraphicsPixmapItem):
    """
    Base class for circuit components (Qubit or Gate).
    """
    def __init__(self, pixmap, component_type: int, component_name: str, grid_size: int):
        super().__init__(pixmap)
        self.component_name = component_name
        self.component_type = component_type
        self.grid_size = grid_size

        self.connected_prev = None
        self.connected_next = None

        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.setFlags(
            QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Ensure the item is selected on click
            if self.scene():
                for item in self.scene().selectedItems():
                    item.setSelected(item == self)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Snap the component to the nearest grid point when the mouse is released.
        """
        # Get the current position of the component
        curr_pos = self.pos()

        # Calculate the nearest grid position
        snapped_x = round(curr_pos.x() / self.grid_size) * self.grid_size
        snapped_y = round(curr_pos.y() / self.grid_size) * self.grid_size

        # Set the new position to the snapped grid position
        self.setPos(QPointF(snapped_x, snapped_y))

        # Check for potential connections
        if self.scene():
            self.scene().check_connections(self)

        # Call the base class implementation to ensure default behavior
        return super().mouseReleaseEvent(event)

class ComponentIcon(QLabel):
    """
    A QLabel subclass for draggable component icons.
    """
    def __init__(self, pixmap: QPixmap, component_name: str, component_type: int):
        super().__init__()
        self.setPixmap(pixmap)
        self.component_name = component_name
        self.component_type = component_type

        self.setFixedSize(pixmap.size())
        self.setObjectName("component-icon")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Component Dragging Operation
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.component_type) + "," + self.component_name)
            drag.setMimeData(mime_data)

            # Drag preview
            drag_pixmap = self.grab()
            drag.setPixmap(drag_pixmap)
            drag.setHotSpot(event.pos())
            drag.exec(Qt.DropAction.CopyAction)


class QuantumToolbar(QScrollArea):
    def __init__(self, parent) -> None:
        super().__init__(parent=parent)
        self.setObjectName("toolbar")

        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setContentsMargins(0, 0, 0, 0)
        self.setFixedWidth(196)

        # Enumerate quantum circuit components
        components = [
            {"name": "qubit-0", "type": TYPE_QUBIT, "pixmap": QPixmap("qubit-0.png"), "pos": (1, 0)},
            {"name": "qubit-1", "type": TYPE_QUBIT, "pixmap": QPixmap("qubit-1.png"), "pos": (1, 1)},
            {"name": "Pauli-X", "type": TYPE_GATE, "pixmap": QPixmap("Pauli-X.png"), "pos": (3, 0)},
            {"name": "Pauli-Y", "type": TYPE_GATE, "pixmap": QPixmap("Pauli-Y.png"), "pos": (3, 1)},
            {"name": "Pauli-Z", "type": TYPE_GATE, "pixmap": QPixmap("Pauli-Z.png"), "pos": (4, 0)}
        ]

        main = QWidget(self)

        grid = QGridLayout(main)
        grid.addWidget(QLabel("Qubits"), 0, 0, 1, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel("Quantum Gates"), 2, 0, 1, 2, Qt.AlignmentFlag.AlignLeft)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(5, 1)

        # Populate palette with components
        for component in components:
            grid.addWidget(ComponentIcon(component["pixmap"], component["name"], component["type"]), *component["pos"])
        
        self.setWidget(main)
        self.setWidgetResizable(True)

class SimulationScene(QGraphicsScene):
    def __init__(self, parent):
        super().__init__(parent=parent)

    def check_connections(self, component: CircuitComponent):
        """
        Check if the given component should connect to another.
        """
        print("Checking connections...")

        if component.component_type == TYPE_QUBIT:
            return  # Qubits cannot connect to other qubits

        # Iterate through all items in the scene
        for item in self.items():
            if item == component or not isinstance(item, CircuitComponent):
                continue

            # Ensure connection is valid (qubit <-> gate)
            if component.component_type == TYPE_GATE and item.component_type == TYPE_QUBIT:
                # Check distance (manhattan length)
                distance = (component.pos() - item.pos()).manhattanLength()

                if distance <= component.grid_size * 8:  # Allow some tolerance
                    # Replace existing connection if there is any
                    if item.connected_next != component:
                        self.removeItem(item.connected_next)

                    # Align component (gate) to item (qubit)
                    component.setPos(item.x() + component.grid_size * 6, item.y())

                    # Establish two-way connection
                    component.connected_prev = item
                    item.connected_next = component
                    self.add_connection_line(item, component)

                    # Return immediately to only connect to one (1) qubit
                    return
                
    def add_connection_line(self, qubit: CircuitComponent, gate: CircuitComponent):
        """
        Draw a line to represent the connection between a qubit and a gate.
        """
        # Remove any existing connection lines
        for item in self.items():
            if isinstance(item, QGraphicsLineItem):
                if getattr(item, "qubit", None) == qubit and getattr(item, "gate", None) == gate:
                    self.removeItem(item)

        # Add a new connection line
        line = QGraphicsLineItem(
            qubit.x() + qubit.pixmap().width(),
            qubit.y() + qubit.pixmap().height() / 2,
            gate.x(),
            gate.y() + gate.pixmap().height() / 2
        )
        line.setPen(QColor("black"))
        line.qubit = qubit
        line.gate = gate
        self.addItem(line)

class SimulationWindow(QGraphicsView):
    def __init__(self, parent) -> None:
        super().__init__(parent=parent)
        self.setObjectName("simulation-window")
        self.setContentsMargins(0, 0, 0, 0)

        self.gridColor = {
            "fg": "#D7D7D7",
            "bg": "#F5F5F5"
        }

        self.scene : QGraphicsScene = SimulationScene(self)
        self.scene.setSceneRect(0, 0, WIN_WIDTH, WIN_HEIGHT)
        self.scale = 24
        self._initGridBackground(self.scene, self.scale)
        self.setScene(self.scene)

        self.setAcceptDrops(True)

    def _initGridBackground(self, scene: QGraphicsScene, scale: int = 16):
        # Create a transparent texture of size W * H
        gridTexture = QPixmap(scale, scale)
        gridTexture.fill(QColor(self.gridColor["bg"]))

        # Draw perpendicular lines across the texture
        painter : QPainter = QPainter(gridTexture)
        painter.setPen(QColor(self.gridColor["fg"]))
        painter.drawLine(0, 0, 0, scale - 1)
        painter.drawLine(0, 0, scale - 1, 0)
        painter.end()

        self.scene.setBackgroundBrush(QBrush(gridTexture))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasText():
            data = event.mimeData().text().split(",")

            component_type: int = int(data[0]) if data[0].isnumeric() else TYPE_QUBIT
            
            component_name: str = data[1]

            pixmap = QPixmap(f"{component_name}.png")

            item = CircuitComponent(pixmap, component_type, component_name, self.scale)
            itemPosition = self.mapToScene(event.position().toPoint())

            item.setPos(itemPosition - QPointF(itemPosition.x() % self.scale, itemPosition.y() % self.scale))
            self.scene.addItem(item)
            event.acceptProposedAction()




class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(WIN_WIDTH, WIN_HEIGHT)
        self.setWindowTitle("Quantum Circuits Simulation Software")
        self.setContentsMargins(0, 0, 0, 0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Initialize main widget container
        main = QWidget(self)
        main.setObjectName("main")

        self.quantumToolbar = QuantumToolbar(main)
        self.simulationWindow = SimulationWindow(main)
        

        # Add all layers to "main"
        layout = QHBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.quantumToolbar)
        layout.addWidget(self.simulationWindow)


        # Set "main" as main widget
        self.setCentralWidget(main)

        # Open and read the css as stylesheet of the app
        with open("styles.css") as f:
            style = f.read()
        self.setStyleSheet(style)

def runApp():
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont("Montserrat-Medium.ttf")

    defFont = QFont("Montserrat Medium", 9)
    defFont.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.36)
    defFont.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(defFont)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    runApp()