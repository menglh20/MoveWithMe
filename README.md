# 🕹️ **MoveWithMe**

*A motion-based memory game built with the Xiao ESP32-C3*

------

## 📘 **Overview**

**MoveWithMe** is an interactive, motion-based reaction game built around the Xiao ESP32-C3. The game presents one movement command at a time, and the player must physically perform the correct direction—up, down, left, or right—within a strict time limit. Each successful action advances the sequence, increasing both difficulty and pace as the game continues.

By requiring real, full-arm movements and fast interpretation of visual cues, MoveWithMe encourages players to stay physically active, while also training focus, reaction speed, and short-term memory. The combination of motion input, real-time feedback, and progressive challenge creates a playful but engaging experience that blends exercise with cognitive stimulation.

------

## 🎮 **How the Game Works**

MoveWithMe has three difficulty settings:

- **Easy**
- **Medium**
- **Hard**

The player selects the difficulty using a rotary encoder, and presses a button to begin the game.

Gameplay follows this cycle:

1. **Calibration Phase**
   The device displays a loading screen and performs a 5-second accelerometer baseline calibration. The player must keep the controller still.
2. **Level Start Screen**
    The OLED shows the difficulty level and the current level number.
    Press the button to continue.
3. **Command Sequence Generation**
    Each level generates `level + 2` movement commands randomly from:
   - Up
   - Down
   - Left
   - Right
4. **One Command at a Time**
   - The OLED displays one arrow.
   - The NeoPixel turns **yellow** to signal input required.
   - A **per-command time limit** (instead of per-level) begins.
   - The **first detected valid movement** must match the displayed command.
5. **Player Input via Accelerometer**
    The ADXL345 detects motion direction using:
   - Zero-offset calibration
   - EMA low-pass filtering
   - Improved directional detection logic
6. **Feedback**
   - Correct → NeoPixel turns **green**, next command appears
   - Wrong or timeout → NeoPixel turns **red**, **Game Over**
7. **Ending Conditions**
   - If the player completes all commands → **Game Win screen**
   - Otherwise → **Game Over** with option to restart

------

## 🔧 **Hardware Components Included**

This project uses a variety of hardware modules beyond the ESP32-C3:

### **Sensors**

- **ADXL345 Accelerometer**
   Used for directional movement detection.

### **Inputs**

- **Rotary Encoder**
   Used for difficulty selection and menu navigation.
- **Push Button**
   Used to confirm selections, start levels, and restart the game.

### **Outputs**

- **SSD1306 128×64 OLED Display**
   Displays arrows, prompts, and game state screens.
- **NeoPixel RGB LED**
   Indicates game status (ready, correct, incorrect, win).

### **Power**

- **LiPo Battery**
   Provides portable power to the device.
- **On/Off Switch**
   Allows controlled shutdown and power management.

------

## 📦 **Enclosure Design Thought Process**

The enclosure was designed with both **ergonomics** and **gameplay clarity** in mind.

### **1. Handheld Form Factor**

The game relies on motion detection, so the enclosure needed to be:

- Lightweight
- Compact
- Comfortable to hold
- Stable enough to perform controlled movements

This led to smooth edges, a symmetrical body, and a grip-friendly shape.

### **2. Sensor Orientation**

The ADXL345 must stay in a consistent orientation for reliable directional detection.
 The enclosure includes:

- A fixed mount for the accelerometer
- Center alignment to avoid torque imbalance

### **3. Screen Visibility**

The OLED is placed on the front face with a slight angle so:

- The player can see arrows clearly while moving

### **4. Accessibility of Controls**

The rotary encoder and button are placed:

- Easily reachable without changing hand position
- Away from areas where accidental presses could occur during movement

### **5. LED Visibility**

The NeoPixel is placed near the display for unified visual feedback:

- Yellow: ready for input
- Green: correct
- Red: incorrect

### **6. Battery & Internal Layout**

The enclosure includes:

- A dedicated space for the LiPo battery
- A secure slot for the Xiao ESP32-C3
- A mounting point for the power switch

These design choices create a sturdy, easy-to-assemble enclosure that supports both the technical requirements and user experience of the game.

------

## 📁 **Repository Structure**

```
MoveWithMe/
│
├── Code/                # Main game logic, sensor filtering, display, controls
├── Hardware/
│   ├── KiCad/           # Schematic (as required in documentation)
│   └── BlockDiagram/
├── Documentation/
│   ├── SystemDiagram.png
│   ├── Schematic.kicad_sch
│   └── README.md        # This file
└── Enclosure/
    ├── CAD Files        # Fusion360 or STL
    └── Renders
```

------

## 🧪 **Future Improvements**

- Multi-LED feedback animations
- Sound output via buzzer
- Wireless high-score tracking
- Multi-command speed mode
- Dynamic difficulty scaling
