import mysql.connector
from mysql.connector import Error
from pathlib import Path
from typing import List, Optional
from datetime import date
import shutil
import subprocess
from .models import Participant, Study, File, StudyParticipant
from ..config import MYSQL_CONFIG

class DatabaseManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not DatabaseManager._initialized:
            self._init_database()
            DatabaseManager._initialized = True

    def _get_connection(self, database: Optional[str] = None):
        cfg = dict(MYSQL_CONFIG)
        if database is None:
            cfg = {k: v for k, v in cfg.items() if k != 'database'}
        return mysql.connector.connect(**cfg)

    def _init_database(self):
        schema_path = Path(__file__).parent / "database_schema.sql"
        try:
            conn = self._get_connection(database=None)
            cursor = conn.cursor()

            cursor.execute("SHOW DATABASES LIKE %s", (MYSQL_CONFIG['database'],))
            if not cursor.fetchone():
                cursor.execute(
                    f"CREATE DATABASE `{MYSQL_CONFIG['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )

            cursor.execute(f"USE `{MYSQL_CONFIG['database']}`;")

            if schema_path.exists():
                sql = schema_path.read_text(encoding='utf-8')
                for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
                    try:
                        cursor.execute(stmt)
                    except mysql.connector.Error as e:
                        if e.errno in (1050, 1061):
                            pass  
                        else:
                            raise
                conn.commit()

        except Error as e:
            raise
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
                
    def create_backup(self) -> Path:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"database_backup_{timestamp}.sql"
        cmd = [
            "mysqldump",
            "-h", MYSQL_CONFIG.get("host", "127.0.0.1"),
            "-P", str(MYSQL_CONFIG.get("port", 3306)),
            "-u", MYSQL_CONFIG.get("user"),
            f"-p{MYSQL_CONFIG.get('password')}",
            MYSQL_CONFIG.get("database"),
        ]
        try:
            with open(backup_path, "wb") as out:
                subprocess.run(cmd, check=True, stdout=out)
            return backup_path
        except Exception as e:
            raise RuntimeError(f"Backup failed: {e}")


    def _execute(self, query: str, params: tuple = (), fetchone=False, fetchall=False, commit=False):
        conn = self._get_connection()
        try:
            conn.database = MYSQL_CONFIG['database']
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            result = None
            if fetchone:
                result = cursor.fetchone()
            elif fetchall:
                result = cursor.fetchall()
            if commit:
                conn.commit()
            return result
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    def add_participant(self, participant: Participant) -> int:
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            conn.database = MYSQL_CONFIG['database']
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Participants (name, surname, code) VALUES (%s, %s, %s)",
                (participant.name, participant.surname, participant.code)
            )
            participant_id = cursor.lastrowid
            conn.commit()
            return int(participant_id) if participant_id else 0
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    def add_participants_to_study_batch(self, study_id: int, participant_ids: List[int]) -> bool:
        if not participant_ids:
            return True
        
        conn = None
        cursor = None
        
        try:
            conn = self._get_connection()
            conn.database = MYSQL_CONFIG['database']
            cursor = conn.cursor()
            
            values = [(study_id, pid) for pid in participant_ids]
            
            
            cursor.executemany(
                "INSERT INTO Study_has_Participants (Study_id_study, Participants_id_participant) VALUES (%s, %s)",
                values
            )
            
            conn.commit()
            
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM Study_has_Participants WHERE Study_id_study=%s",
                (study_id,)
            )
            result = cursor.fetchone()
            count = result[0] if result else 0
            
            
            if count != len(participant_ids):
                return False
            
            return True
            
        except Exception as e:
            import traceback            
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            
            return False
            
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_participant(self, participant_id: int) -> Optional[Participant]:
        row = self._execute("SELECT * FROM Participants WHERE id_participant = %s", (participant_id,), fetchone=True)
        if row:
            return Participant(id_participant=row['id_participant'], name=row['name'], surname=row['surname'], code=row['code'])
        return None

    def get_all_participants(self) -> List[Participant]:
        rows = self._execute("SELECT * FROM Participants ORDER BY surname, name", fetchall=True)
        return [Participant(id_participant=r['id_participant'], name=r['name'], surname=r['surname'], code=r['code']) for r in (rows or [])]

    def update_participant(self, participant: Participant) -> bool:
        self._execute(
            "UPDATE Participants SET name=%s, surname=%s, code=%s WHERE id_participant=%s",
            (participant.name, participant.surname, participant.code, participant.id_participant),
            commit=True
        )
        return self.get_participant(participant.id_participant) is not None

    def delete_participant(self, participant_id: int) -> bool:
        try:
            self._execute(
                "DELETE FROM Participants WHERE id_participant = %s", 
                (participant_id,), 
                commit=True
            )
            return True
        except Error as e:
            return False

    def add_study(self, study: Study) -> int:
        conn = None
        cursor = None
        
        try:
            conn = self._get_connection()
            conn.database = MYSQL_CONFIG['database']
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO Study (`name`, `type_id`, `date`, `path`) VALUES (%s, %s, %s, %s)",
                (study.name, study.type_id, (study.date.isoformat() if study.date else None), study.path)
            )
            
            study_id = cursor.lastrowid
            
            conn.commit()
            
            return study_id
            
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
            
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_study(self, study_id: int) -> Optional[Study]:
        row = self._execute(
            "SELECT s.*, st.name as type_name FROM Study s "
            "LEFT JOIN StudyTypes st ON s.type_id = st.id_type "
            "WHERE s.id_study = %s",
            (study_id,),
            fetchone=True
        )
        if row:
            study_date = None
            if row.get('date'):
                if isinstance(row['date'], str):
                    study_date = date.fromisoformat(row['date'])
                else:
                    study_date = row['date']
                    
            return Study(
                id_study=row['id_study'],
                name=row['name'],
                type_id=row['type_id'],
                type_name=row.get('type_name', ''),
                date=study_date,
                path=row.get('path')
            )
        return None

    def get_all_studies(self) -> List[Study]:
        rows = self._execute(
            "SELECT s.*, st.name as type_name FROM Study s "
            "LEFT JOIN StudyTypes st ON s.type_id = st.id_type "
            "ORDER BY s.date DESC",
            fetchall=True
        )
        out = []
        for r in (rows or []):
            study_date = None
            if r.get('date'):
                if isinstance(r['date'], str):
                    study_date = date.fromisoformat(r['date'])
                else:
                    study_date = r['date']
                    
            out.append(Study(
                id_study=r['id_study'],
                name=r['name'],
                type_id=r['type_id'],
                type_name=r.get('type_name', ''),
                date=study_date,
                path=r.get('path')
            ))
        return out

    def update_study(self, study: Study) -> bool:
        self._execute(
            "UPDATE Study SET name=%s, type_id=%s, date=%s, path=%s WHERE id_study=%s",
            (study.name, study.type_id, (study.date.isoformat() if study.date else None), study.path, study.id_study),
            commit=True
        )
        return True

    def delete_study(self, study_id: int) -> bool:
        self._execute("DELETE FROM File WHERE Study_id_study = %s", (study_id,), commit=True)
        self._execute("DELETE FROM Study_has_Participants WHERE Study_id_study = %s", (study_id,), commit=True)
        self._execute("DELETE FROM Study WHERE id_study = %s", (study_id,), commit=True)
        return True

    def add_participant_to_study(self, study_id: int, participant_id: int) -> bool:
        try:
            self._execute("INSERT INTO Study_has_Participants (Study_id_study, Participants_id_participant) VALUES (%s, %s)", (study_id, participant_id), commit=True)
            return True
        except Error:
            return False

    def remove_participant_from_study(self, study_id: int, participant_id: int) -> bool:
        self._execute("DELETE FROM Study_has_Participants WHERE Study_id_study=%s AND Participants_id_participant=%s", (study_id, participant_id), commit=True)
        return True

    def get_study_participants(self, study_id: int) -> List[Participant]:
        rows = self._execute(
            "SELECT p.* FROM Participants p JOIN Study_has_Participants sp ON p.id_participant = sp.Participants_id_participant WHERE sp.Study_id_study = %s ORDER BY p.surname, p.name",
            (study_id,),
            fetchall=True
        )
        return [Participant(id_participant=r['id_participant'], name=r['name'], surname=r['surname'], code=r['code']) for r in (rows or [])]

    def get_participant_studies(self, participant_id: int) -> List[Study]:
        rows = self._execute(
            "SELECT s.* FROM Study s JOIN Study_has_Participants sp ON s.id_study = sp.Study_id_study WHERE sp.Participants_id_participant = %s ORDER BY s.date DESC",
            (participant_id,),
            fetchall=True
        )
        out = []
        for r in (rows or []):
            study_date = None
            if r.get('date'):
                if isinstance(r['date'], str):
                    study_date = date.fromisoformat(r['date'])
                else:
                    study_date = r['date']
                
            out.append(Study(
                id_study=r['id_study'],
                name=r['name'],
                type_id=r['type_id'],
                date=study_date
            ))
        return out

    def add_file(self, file: File) -> int:
        self._execute("INSERT INTO File (name, file_path, Study_id_study) VALUES (%s, %s, %s)", (file.name, file.file_path, file.study_id), commit=True)
        conn = self._get_connection()
        try:
            conn.database = MYSQL_CONFIG['database']
            cursor = conn.cursor()
            cursor.execute("SELECT LAST_INSERT_ID()")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    def get_file(self, file_id: int) -> Optional[File]:
        row = self._execute("SELECT * FROM File WHERE id_file = %s", (file_id,), fetchone=True)
        if row:
            return File(id_file=row['id_file'], name=row['name'], file_path=row['file_path'], study_id=row['Study_id_study'])
        return None

    def get_study_files(self, study_id: int) -> List[File]:
        rows = self._execute("SELECT * FROM File WHERE Study_id_study = %s ORDER BY name", (study_id,), fetchall=True)
        return [File(id_file=r['id_file'], name=r['name'], file_path=r['file_path'], study_id=r['Study_id_study']) for r in (rows or [])]

    def get_study_types(self) -> List[tuple]:
        try:
            rows = self._execute("SELECT id_type, name FROM StudyTypes ORDER BY name", fetchall=True)
            return [(r['id_type'], r['name']) for r in (rows or [])]
        except Exception as e:
            return []

    def add_study_type(self, type_name: str) -> bool:
        try:
            self._execute(
                "INSERT IGNORE INTO StudyTypes (name) VALUES (%s)",
                (type_name.strip(),),
                commit=True
            )
            return True
        except Error as e:
            return False

    def get_all_files(self) -> List[File]:
        rows = self._execute("SELECT * FROM File ORDER BY name", fetchall=True)
        return [File(id_file=r['id_file'], name=r['name'], file_path=r['file_path'], study_id=r['Study_id_study']) for r in (rows or [])]

    def update_file(self, file: File) -> bool:
        self._execute("UPDATE File SET name=%s, file_path=%s, Study_id_study=%s WHERE id_file=%s", (file.name, file.file_path, file.study_id, file.id_file), commit=True)
        return True

    def delete_file(self, file_id: int) -> bool:
        self._execute("DELETE FROM File WHERE id_file = %s", (file_id,), commit=True)
        return True

    def scan_study_files(self, study_id: int) -> int:
        study = self.get_study(study_id)
        if not study or not study.path:
            return 0
        from pathlib import Path
        study_path = Path(study.path)
        if not study_path.exists():
            return 0
        added = 0
        for c3d_file in study_path.rglob("*.c3d"):
            rows = self._execute("SELECT id_file FROM File WHERE file_path = %s", (str(c3d_file),), fetchall=True)
            if not rows:
                file = File(name=c3d_file.name, file_path=str(c3d_file), study_id=study_id)
                self.add_file(file)
                added += 1
        return added
    
    def update_study_type(self, type_id: int, new_name: str) -> bool:
        try:
            self._execute(
                "UPDATE StudyTypes SET name=%s WHERE id_type=%s",
                (new_name.strip(), type_id),
                commit=True
            )
            return True
        except Error as e:
            return False

    def delete_study_type(self, type_id: int) -> bool:
        try:
            self._execute(
                "DELETE FROM StudyTypes WHERE id_type=%s",
                (type_id,),
                commit=True
            )
            return True
        except Error as e:
            return False

    def get_studies_by_type(self, type_id: int) -> List[Study]:
        try:
            rows = self._execute(
                """
                SELECT s.*, st.name as type_name 
                FROM Study s 
                LEFT JOIN StudyTypes st ON s.type_id = st.id_type 
                WHERE s.type_id = %s
                ORDER BY s.date DESC
                """,
                (type_id,),
                fetchall=True
            )
            
            if not rows:
                return []
            
            return [
                Study(
                    id_study=r['id_study'],
                    name=r['name'],
                    type_id=r['type_id'],
                    type_name=r.get('type_name'),
                    date=r['date'],
                    path=r['path']
                )
                for r in rows
            ]
        except Exception as e:
            return []
    
