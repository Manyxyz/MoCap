from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Participant:
    id_participant: Optional[int] = None
    name: str = ""
    surname: str = ""
    code: str = ""
    
    @property
    def full_name(self) -> str:
        return f"{self.name} {self.surname}".strip()

@dataclass
class Study:
    id_study: Optional[int] = None
    name: str = ""
    type_id: Optional[int] = None  
    type_name: Optional[str] = None  
    date: Optional[date] = None
    path: Optional[str] = None

@dataclass
class File:
    id_file: Optional[int] = None
    name: str = ""
    file_path: Optional[str] = None
    study_id: Optional[int] = None

@dataclass
class StudyParticipant:
    study_id: int
    participant_id: int