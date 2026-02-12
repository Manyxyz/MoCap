CREATE TABLE IF NOT EXISTS StudyTypes (
    id_type INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(90) UNIQUE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Participants (
    id_participant INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(45) NOT NULL,
    surname VARCHAR(45) NOT NULL,
    code VARCHAR(45) UNIQUE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Study (
    id_study INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(90) NOT NULL,
    type_id INT NOT NULL,
    date DATE,
    path VARCHAR(255),
    FOREIGN KEY (type_id) REFERENCES StudyTypes(id_type) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Study_has_Participants (
    Study_id_study INT NOT NULL,
    Participants_id_participant INT NOT NULL,
    PRIMARY KEY (Study_id_study, Participants_id_participant),
    FOREIGN KEY (Study_id_study) REFERENCES Study(id_study) ON DELETE CASCADE,
    FOREIGN KEY (Participants_id_participant) REFERENCES Participants(id_participant) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS File (
    id_file INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(90) NOT NULL,
    file_path VARCHAR(255),
    Study_id_study INT,
    FOREIGN KEY (Study_id_study) REFERENCES Study(id_study) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Create indexes
ALTER TABLE Participants ADD INDEX idx_participants_code (code);
ALTER TABLE Participants ADD INDEX idx_participants_surname (surname);
ALTER TABLE Study ADD INDEX idx_study_name (name);
ALTER TABLE Study ADD INDEX idx_study_path (path);
ALTER TABLE Study ADD INDEX idx_study_type (type_id);
ALTER TABLE File ADD INDEX idx_file_study (Study_id_study);
ALTER TABLE Study_has_Participants ADD INDEX idx_study_participants_study (Study_id_study);
ALTER TABLE Study_has_Participants ADD INDEX idx_study_participants_participant (Participants_id_participant);