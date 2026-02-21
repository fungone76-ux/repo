"""World loading system.

Supports both legacy single-file and modern modular folder formats.
Each world is a complete universe that defines genre, narrative style,
characters, quests, locations, and atmosphere.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from luna.core.models import (
    CompanionDefinition,
    EndgameDefinition,
    GlobalEventDefinition,
    GlobalEventEffect,
    Location,
    LocationState,
    MilestoneDefinition,
    NarrativeArc,
    QuestAction,
    QuestCondition,
    QuestDefinition,
    QuestRewards,
    QuestStage,
    QuestTransition,
    ScheduleEntry,
    StoryBeat,
    TimeOfDay,
    TimeSlot,
    WorldDefinition,
)
from luna.core.config import get_settings


class WorldLoadError(Exception):
    """Error loading world data."""
    pass


class WorldValidator:
    """Validates world data structure."""
    
    @staticmethod
    def validate_world(data: Dict[str, Any]) -> List[str]:
        """Validate world data and return list of errors.
        
        Args:
            data: Raw world data
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Required sections
        if "meta" not in data:
            errors.append("Missing required section: meta")
        else:
            meta = data["meta"]
            if "id" not in meta:
                errors.append("meta.id is required")
            if "name" not in meta:
                errors.append("meta.name is required")
        
        if "companions" not in data or not data["companions"]:
            errors.append("Missing or empty section: companions")
        
        # Validate companions
        if "companions" in data:
            for name, companion in data["companions"].items():
                if not isinstance(companion, dict):
                    errors.append(f"companion.{name} must be a dictionary")
                    continue
                
                if "base_prompt" not in companion:
                    errors.append(f"companion.{name} missing base_prompt")
        
        # Validate quests
        if "quests" in data:
            for quest_id, quest in data["quests"].items():
                errors.extend(WorldValidator._validate_quest(quest_id, quest))
        
        return errors
    
    @staticmethod
    def _validate_quest(quest_id: str, quest: Dict[str, Any]) -> List[str]:
        """Validate quest structure."""
        errors = []
        
        if "meta" not in quest:
            errors.append(f"quest.{quest_id} missing meta")
        
        if "stages" not in quest or not quest["stages"]:
            errors.append(f"quest.{quest_id} has no stages")
        
        # Check transitions reference valid stages
        if "stages" in quest:
            stage_ids = set(quest["stages"].keys())
            stage_ids.add("_complete")
            stage_ids.add("_fail")
            
            for stage_id, stage in quest["stages"].items():
                if "transitions" in stage:
                    for trans in stage["transitions"]:
                        target = trans.get("target_stage") or trans.get("target")
                        if target and target not in stage_ids:
                            errors.append(
                                f"quest.{quest_id}.stage.{stage_id} references "
                                f"unknown stage: {target}"
                            )
        
        return errors


class WorldLoader:
    """Loads and parses world definitions from YAML files.
    
    Supports two formats:
    - Legacy: Single YAML file (world_name.yaml)
    - Modular: Directory with multiple YAML files (world_name/*.yaml)
    """
    
    def __init__(self, worlds_path: Optional[Path] = None) -> None:
        """Initialize world loader.
        
        Args:
            worlds_path: Path to worlds directory. Uses config default if None.
        """
        settings = get_settings()
        self.worlds_path = worlds_path or settings.worlds_path
        self._cache: Dict[str, WorldDefinition] = {}
    
    def list_worlds(self) -> List[Dict[str, Any]]:
        """List all available worlds.
        
        Returns:
            List of world metadata dicts with keys:
            - id: World identifier
            - name: Display name
            - genre: World genre
            - description: Short description
            - format: 'legacy' or 'modular'
        """
        worlds = []
        
        if not self.worlds_path.exists():
            return worlds
        
        # Legacy YAML files
        for file_path in self.worlds_path.glob("*.yaml"):
            try:
                data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
                meta = data.get("meta", {})
                worlds.append({
                    "id": meta.get("id", file_path.stem),
                    "name": meta.get("name", file_path.stem),
                    "genre": meta.get("genre", "Unknown"),
                    "description": meta.get("description", ""),
                    "format": "legacy",
                    "filename": file_path.name,
                })
            except Exception as e:
                print(f"Warning: Error loading world file {file_path}: {e}")
        
        # Modular folders
        for folder_path in self.worlds_path.iterdir():
            if folder_path.is_dir() and (folder_path / "_meta.yaml").exists():
                try:
                    meta_data = yaml.safe_load(
                        (folder_path / "_meta.yaml").read_text(encoding="utf-8")
                    )
                    meta = meta_data.get("meta", {})
                    worlds.append({
                        "id": meta.get("id", folder_path.name),
                        "name": meta.get("name", folder_path.name),
                        "genre": meta.get("genre", "Unknown"),
                        "description": meta.get("description", ""),
                        "format": "modular",
                        "filename": folder_path.name,
                    })
                except Exception as e:
                    print(f"Warning: Error loading world folder {folder_path}: {e}")
        
        return sorted(worlds, key=lambda w: w["name"])
    
    def load_world(self, world_id: str) -> Optional[WorldDefinition]:
        """Load world definition.
        
        Auto-detects format (legacy file or modular folder).
        
        Args:
            world_id: World identifier (filename without extension for legacy,
                     folder name for modular)
            
        Returns:
            WorldDefinition or None if not found/invalid
        """
        # Check cache
        if world_id in self._cache:
            return self._cache[world_id]
        
        # Try modular folder first
        folder_path = self.worlds_path / world_id
        if folder_path.is_dir() and (folder_path / "_meta.yaml").exists():
            world = self._load_modular(folder_path, world_id)
        else:
            # Try legacy file
            file_path = self.worlds_path / f"{world_id}.yaml"
            if not file_path.exists():
                file_path = self.worlds_path / world_id
            
            if file_path.exists():
                world = self._load_legacy(file_path, world_id)
            else:
                return None
        
        if world:
            self._cache[world_id] = world
        
        return world
    
    def clear_cache(self) -> None:
        """Clear world cache."""
        self._cache.clear()
    
    def _load_legacy(
        self, 
        file_path: Path, 
        world_id: str,
    ) -> Optional[WorldDefinition]:
        """Load legacy single-file world format.
        
        Args:
            file_path: Path to YAML file
            world_id: World identifier
            
        Returns:
            WorldDefinition or None
        """
        try:
            raw_data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            return self._process_world_data(raw_data, world_id)
        except Exception as e:
            print(f"Error loading legacy world {world_id}: {e}")
            return None
    
    def _load_modular(
        self, 
        folder_path: Path, 
        world_id: str,
    ) -> Optional[WorldDefinition]:
        """Load modular folder world format.
        
        Merges data from multiple YAML files in the folder.
        
        Args:
            folder_path: Path to world folder
            world_id: World identifier
            
        Returns:
            WorldDefinition or None
        """
        try:
            merged_data: Dict[str, Any] = {
                "meta": {},
                "npc_logic": {},
                "companions": {},
                "locations": {},
                "quests": {},
                "milestones": {},
                "time": {},
                "global_events": {},
            }
            
            # Load _meta.yaml first
            meta_file = folder_path / "_meta.yaml"
            if meta_file.exists():
                meta_data = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
                merged_data["meta"] = meta_data.get("meta", {})
                merged_data["npc_logic"] = meta_data.get("npc_logic", {})
                merged_data["player_character"] = meta_data.get("player_character", {})
                merged_data["endgame"] = meta_data.get("endgame", {})
                merged_data["visual_style"] = meta_data.get("visual_style", {})
            
            # Load all other YAML files
            for yaml_file in folder_path.glob("*.yaml"):
                if yaml_file.name == "_meta.yaml":
                    continue
                
                try:
                    file_data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                    if not file_data:
                        continue
                    
                    # Merge companions
                    if "companion" in file_data:
                        companion = file_data["companion"]
                        name = companion.get("name", yaml_file.stem)
                        merged_data["companions"][name] = companion
                    
                    if "companions" in file_data:
                        merged_data["companions"].update(file_data["companions"])
                    
                    # Merge quests
                    if "quests" in file_data:
                        merged_data["quests"].update(file_data["quests"])
                    
                    # Merge locations
                    if "locations" in file_data:
                        if isinstance(file_data["locations"], list):
                            for loc in file_data["locations"]:
                                if isinstance(loc, dict) and "id" in loc:
                                    merged_data["locations"][loc["id"]] = loc
                        else:
                            merged_data["locations"].update(file_data["locations"])
                    
                    # Merge time slots
                    if "time" in file_data:
                        merged_data["time"].update(file_data["time"])
                    
                    # Merge global events
                    if "global_events" in file_data:
                        merged_data["global_events"].update(file_data["global_events"])
                    
                    # Merge milestones from companion files
                    if "milestones" in file_data:
                        for milestone in file_data["milestones"]:
                            if isinstance(milestone, dict) and "id" in milestone:
                                merged_data["milestones"][milestone["id"]] = milestone
                    
                except Exception as e:
                    print(f"Warning: Error loading {yaml_file.name}: {e}")
            
            return self._process_world_data(merged_data, world_id)
            
        except Exception as e:
            print(f"Error loading modular world {world_id}: {e}")
            return None
    
    def _process_world_data(
        self, 
        data: Dict[str, Any], 
        world_id: str,
    ) -> Optional[WorldDefinition]:
        """Process raw world data into WorldDefinition.
        
        Args:
            data: Raw merged world data
            world_id: World identifier
            
        Returns:
            WorldDefinition or None
        """
        # Validate
        errors = WorldValidator.validate_world(data)
        if errors:
            print(f"Validation errors for world {world_id}:")
            for error in errors:
                print(f"  - {error}")
            return None
        
        meta = data.get("meta", {})
        
        # Process companions
        companions = {}
        for name, comp_data in data.get("companions", {}).items():
            companions[name] = self._process_companion(name, comp_data)
        
        # Process locations (full Location System V2 support)
        locations = {}
        for loc_id, loc_data in data.get("locations", {}).items():
            # Convert time_descriptions keys to TimeOfDay enum
            time_desc = {}
            for time_key, desc in loc_data.get("time_descriptions", {}).items():
                try:
                    time_desc[TimeOfDay(time_key)] = desc
                except ValueError:
                    print(f"Warning: Invalid time in time_descriptions for {loc_id}: {time_key}")
            
            # Convert available_times to TimeOfDay list
            available_times = []
            for time_key in loc_data.get("available_times", []):
                try:
                    available_times.append(TimeOfDay(time_key))
                except ValueError:
                    print(f"Warning: Invalid time in available_times for {loc_id}: {time_key}")
            
            locations[loc_id] = Location(
                id=loc_id,
                name=loc_data.get("name", loc_id),
                description=loc_data.get("description", ""),
                visual_style=loc_data.get("visual_style", ""),
                lighting=loc_data.get("lighting", ""),
                # Navigation
                connected_to=loc_data.get("connected_to", []),
                parent_location=loc_data.get("parent_location"),
                sub_locations=loc_data.get("sub_locations", []),
                aliases=loc_data.get("aliases", []),
                # Access control
                requires_parent=loc_data.get("requires_parent", False),
                requires_item=loc_data.get("requires_item"),
                requires_flag=loc_data.get("requires_flag"),
                hidden=loc_data.get("hidden", False),
                discovery_hint=loc_data.get("discovery_hint", ""),
                # Time-based
                available_times=available_times,
                closed_description=loc_data.get("closed_description", ""),
                # NPCs
                available_characters=loc_data.get("available_characters", []),
                companion_can_follow=loc_data.get("companion_can_follow", True),
                companion_refuse_message=loc_data.get("companion_refuse_message", ""),
                # Dynamic descriptions
                dynamic_descriptions=loc_data.get("dynamic_descriptions", {}),
                time_descriptions=time_desc,
            )
        
        # Process time slots
        time_slots = {}
        for time_key, time_data in data.get("time", {}).items():
            try:
                time_of_day = TimeOfDay(time_key)
                time_slots[time_of_day] = TimeSlot(
                    time_of_day=time_of_day,
                    lighting=time_data.get("lighting", ""),
                    ambient_description=time_data.get("description", ""),
                )
            except ValueError:
                print(f"Warning: Invalid time slot: {time_key}")
        
        # Process quests
        quests = {}
        for quest_id, quest_data in data.get("quests", {}).items():
            try:
                quests[quest_id] = self._process_quest(quest_id, quest_data)
            except Exception as e:
                print(f"Warning: Error processing quest {quest_id}: {e}")
        
        # Process narrative arc (story beats)
        narrative_arc = self._process_narrative_arc(data.get("narrative_arc", {}))
        
        # Get gameplay systems config
        gameplay_systems = data.get("gameplay_systems", {})
        
        # Process milestones (from companion files)
        milestones = {}
        for ms_id, ms_data in data.get("milestones", {}).items():
            try:
                milestones[ms_id] = MilestoneDefinition(
                    id=ms_id,
                    name=ms_data.get("name", ms_id),
                    description=ms_data.get("description", ""),
                    icon=ms_data.get("icon", ""),
                    condition=ms_data.get("condition", {}),
                )
            except Exception as e:
                print(f"Warning: Error processing milestone {ms_id}: {e}")
        
        # Process endgame
        endgame_data = data.get("endgame")
        endgame = None
        if endgame_data:
            try:
                from luna.core.models import EndgameCondition
                conditions = []
                for cond in endgame_data.get("victory_conditions", []):
                    conditions.append(EndgameCondition(**cond))
                endgame = EndgameDefinition(
                    description=endgame_data.get("description", ""),
                    victory_conditions=conditions,
                )
            except Exception as e:
                print(f"Warning: Error processing endgame: {e}")
        
        # Process global events
        global_events = {}
        for evt_id, evt_data in data.get("global_events", {}).items():
            try:
                effects_data = evt_data.get("effects", {})
                effects = GlobalEventEffect(
                    duration=effects_data.get("duration", 3),
                    location_modifiers=effects_data.get("location_modifiers", []),
                    visual_tags=effects_data.get("visual_tags", []),
                    atmosphere_change=effects_data.get("atmosphere_change", ""),
                    affinity_multiplier=effects_data.get("affinity_multiplier", 1.0),
                    on_start=effects_data.get("on_start", []),
                    on_end=effects_data.get("on_end", []),
                )
                
                trigger = evt_data.get("trigger", {})
                global_events[evt_id] = GlobalEventDefinition(
                    id=evt_id,
                    title=evt_data.get("meta", {}).get("title", evt_id),
                    description=evt_data.get("meta", {}).get("description", ""),
                    trigger_type=trigger.get("type", "random"),
                    trigger_chance=trigger.get("chance", 0.1),
                    trigger_conditions=trigger.get("conditions", []),
                    allowed_times=trigger.get("allowed_times", []),
                    effects=effects,
                    narrative_prompt=evt_data.get("narrative_prompt", ""),
                )
            except Exception as e:
                print(f"Warning: Error processing global event {evt_id}: {e}")
        
        # Get player character config
        player_character = data.get("player_character", {})
        
        # Build world definition
        return WorldDefinition(
            id=meta.get("id", world_id),
            name=meta.get("name", world_id),
            genre=meta.get("genre", "Visual Novel"),
            description=meta.get("description", ""),
            lore=meta.get("lore", ""),
            locations=locations,
            companions=companions,
            time_slots=time_slots,
            quests=quests,
            narrative_arc=narrative_arc,
            gameplay_systems=gameplay_systems,
            female_hints=data.get("npc_logic", {}).get("female_hints", []),
            male_hints=data.get("npc_logic", {}).get("male_hints", []),
            milestones=milestones,
            endgame=endgame,
            global_events=global_events,
            player_character=player_character,
        )
    
    def _process_companion(self, name: str, data: Dict[str, Any]) -> CompanionDefinition:
        """Process companion data."""
        # Process schedule (supports both legacy "location" and new "preferred_location")
        schedule = {}
        if "schedule" in data:
            for time_key, sched_data in data["schedule"].items():
                try:
                    time_of_day = TimeOfDay(time_key)
                    # Support both legacy "location" and new "preferred_location"
                    loc = sched_data.get("preferred_location") or sched_data.get("location", "Unknown")
                    schedule[time_of_day] = ScheduleEntry(
                        time_of_day=time_of_day,
                        location=loc,
                        outfit=sched_data.get("outfit", "default"),
                        activity=sched_data.get("activity", ""),
                    )
                except ValueError:
                    print(f"Warning: Invalid schedule time: {time_key}")
        
        # Get personality system data
        personality = data.get("personality_system", {})
        
        return CompanionDefinition(
            name=name,
            role=data.get("role", ""),
            age=data.get("age", 21),
            base_personality=data.get("base_personality", ""),
            base_prompt=data.get("base_prompt", ""),
            default_outfit=data.get("default_outfit", "default"),
            wardrobe=data.get("wardrobe", {}),
            emotional_states=personality.get("emotional_states", {}),
            affinity_tiers=personality.get("affinity_tiers", {}),
            dialogue_tone=data.get("dialogue_tone", {}),
            schedule=schedule,
            relations=data.get("relations", {}),
        )
    
    def _process_narrative_arc(self, data: Dict[str, Any]) -> NarrativeArc:
        """Process narrative arc and story beats."""
        beats = []
        for beat_data in data.get("beats", []):
            try:
                beats.append(StoryBeat(**beat_data))
            except Exception as e:
                print(f"Warning: Error processing story beat: {e}")
        
        return NarrativeArc(
            premise=data.get("premise", ""),
            themes=data.get("themes", []),
            beats=beats,
            hard_limits=data.get("hard_limits", []),
            soft_guidelines=data.get("soft_guidelines", []),
        )
    
    def _process_quest(self, quest_id: str, data: Dict[str, Any]) -> QuestDefinition:
        """Process quest data."""
        # Process stages
        stages = {}
        for stage_id, stage_data in data.get("stages", {}).items():
            # Process on_enter actions
            on_enter = []
            for action_data in stage_data.get("on_enter", []):
                on_enter.append(QuestAction(**action_data))
            
            # Process exit conditions
            exit_conditions = []
            for cond_data in stage_data.get("exit_conditions", []):
                exit_conditions.append(QuestCondition(**cond_data))
            
            # Process transitions
            transitions = []
            for trans_data in stage_data.get("transitions", []):
                # Support both "target" and "target_stage"
                if "target" in trans_data and "target_stage" not in trans_data:
                    trans_data = {**trans_data, "target_stage": trans_data.pop("target")}
                transitions.append(QuestTransition(**trans_data))
            
            stages[stage_id] = QuestStage(
                title=stage_data.get("title", ""),
                description=stage_data.get("description", ""),
                narrative_prompt=stage_data.get("narrative_prompt", ""),
                on_enter=on_enter,
                on_exit=[],  # Not currently used
                exit_conditions=exit_conditions,
                transitions=transitions,
                max_turns=stage_data.get("max_turns"),
            )
        
        # Process activation
        activation = data.get("activation", {})
        activation_conditions = []
        for cond_data in activation.get("conditions", []):
            activation_conditions.append(QuestCondition(**cond_data))
        
        # Process rewards
        rewards_data = data.get("rewards", {})
        rewards = QuestRewards(
            affinity=rewards_data.get("affinity", {}),
            items=rewards_data.get("items", []),
            flags=rewards_data.get("flags", {}),
            unlock_quests=rewards_data.get("unlock_quests", []),
        )
        
        meta = data.get("meta", {})
        
        return QuestDefinition(
            id=quest_id,
            title=meta.get("title", quest_id),
            description=meta.get("description", ""),
            character=meta.get("character"),
            activation_type=activation.get("type", "auto"),
            activation_conditions=activation_conditions,
            trigger_event=activation.get("trigger_event"),
            hidden=meta.get("hidden", False),
            stages=stages,
            start_stage="start" if "start" in stages else list(stages.keys())[0] if stages else "",
            rewards=rewards,
            required_quests=data.get("requires", []),
        )
    
    def get_companion_list(self, world_id: str) -> List[str]:
        """Get list of companion names in world.
        
        Args:
            world_id: World identifier
            
        Returns:
            List of companion names
        """
        world = self.load_world(world_id)
        if not world:
            return []
        return list(world.companions.keys())
    
    def get_companion(
        self, 
        world_id: str, 
        companion_name: str,
    ) -> Optional[CompanionDefinition]:
        """Get specific companion definition.
        
        Args:
            world_id: World identifier
            companion_name: Companion name
            
        Returns:
            CompanionDefinition or None
        """
        world = self.load_world(world_id)
        if not world:
            return None
        return world.companions.get(companion_name)
    
    def get_quest(
        self, 
        world_id: str, 
        quest_id: str,
    ) -> Optional[QuestDefinition]:
        """Get specific quest definition.
        
        Args:
            world_id: World identifier
            quest_id: Quest identifier
            
        Returns:
            QuestDefinition or None
        """
        world = self.load_world(world_id)
        if not world:
            return None
        return world.quests.get(quest_id)


# Singleton instance
_world_loader: Optional[WorldLoader] = None


def get_world_loader() -> WorldLoader:
    """Get or create world loader singleton.
    
    Returns:
        WorldLoader instance
    """
    global _world_loader
    if _world_loader is None:
        _world_loader = WorldLoader()
    return _world_loader
