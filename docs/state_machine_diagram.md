stateDiagram-v2
    [*] --> TRAVERSE: Level Start
    
    TRAVERSE --> STUCK: Stuck detected
    TRAVERSE --> RECOVER: Stats below threshold\nAND loot known
    TRAVERSE --> COMBAT: Enemy visible\nAND ammo > 0
    TRAVERSE --> SCAN: (Damage OR scan_frequency)\nAND scan ready
    
    STUCK --> TRAVERSE: Unstuck\n(moved >150 units)
    
    note right of STUCK
        Highest Priority
        Cannot be interrupted
        Returns to TRAVERSE
    end note
    
    RECOVER --> STUCK: Stuck detected
    RECOVER --> COMBAT: Enemy visible\nIF seeking armor/ammo\nAND ammo > 0
    RECOVER --> TRAVERSE: All stats above threshold
    
    note right of RECOVER
        Priority: Health → Armor → Ammo
        Re-evaluates every frame
        Seeking health: no COMBAT
    end note
    
    COMBAT --> RECOVER: Health < threshold\nOR ammo = 0
    COMBAT --> TRAVERSE: No enemies visible
    
    note right of COMBAT
        Aim, Fire, Strafe
        Fight until threat gone
        or resources critical
    end note
    
    SCAN --> STUCK: Stuck detected
    SCAN --> RECOVER: Stats below threshold
    SCAN --> COMBAT: Enemy visible\nAND ammo > 0
    SCAN --> TRAVERSE: 360° rotation complete
    
    note right of SCAN
        Only from TRAVERSE
        Places dynamic nodes
        Finds hidden enemies/loot
    end note


## Legend
- **STUCK**: Highest priority, fixes navigation issues
- **RECOVER**: Resource seeking (health/armor/ammo)
- **COMBAT**: Engage enemies
- **SCAN**: 360° environmental awareness
- **TRAVERSE**: Default navigation to exit