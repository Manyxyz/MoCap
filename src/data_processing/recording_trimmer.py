import numpy as np
from typing import Tuple, Optional
from PySide6.QtWidgets import QMessageBox, QWidget
from ..ui.message_box import styled_message_box

class RecordingTrimmer:
    
    def __init__(self, parent_widget: Optional[QWidget] = None, main_window_ui=None):
        """
        Initialize trimmer.
        
        Args:
            parent_widget: Parent widget for dialogs (usually MainWindowUI._main_window)
        """
        self.parent_widget = parent_widget
        self.main_window_ui = main_window_ui
        self.undo_stack = [] 
    
    def apply_trim(
        self, 
        frames_data: np.ndarray, 
        trim_start: int, 
        trim_end: int,
        frame_rate: float,
        save_to_undo: bool = True
    ) -> Tuple[np.ndarray, bool]:
        """
        Apply trim to frames_data.
        
        Args:
            frames_data: Original frame data (n_frames, n_markers, 3)
            trim_start: Start frame index (inclusive)
            trim_end: End frame index (inclusive)
            frame_rate: Recording frame rate
            save_to_undo: Whether to save to undo stack
        
        Returns:
            Tuple of (trimmed_data, success)
        """
        if frames_data is None or frames_data.shape[0] == 0:
            return frames_data, False
        

        trim_start = max(0, min(trim_start, frames_data.shape[0] - 1))
        trim_end = max(trim_start, min(trim_end, frames_data.shape[0] - 1))
        

        duration_before = frames_data.shape[0]
        duration_after = trim_end - trim_start + 1
        

        if not self._confirm_trim(
            duration_before, 
            duration_after, 
            trim_start, 
            trim_end, 
            frame_rate
        ):
            return frames_data, False
        

        if save_to_undo and self.main_window_ui:
            undo_action = {
                'type': 'trim',
                'original_data': frames_data.copy(),
                'trim_start': trim_start,
                'trim_end': trim_end
            }
            self.main_window_ui._undo_stack.append(undo_action)
            self.main_window_ui._redo_stack.clear()
        

        trimmed_data = frames_data[trim_start:trim_end + 1, :, :]
        

        self._show_success(duration_after, frame_rate)
        
        return trimmed_data, True
    
    def undo_last_trim(self) -> Optional[np.ndarray]:
        """
        Undo last trim operation.
        
        Returns:
            Original data if undo successful, None otherwise
        """
        if not self.undo_stack:
            return None
        
        action = self.undo_stack.pop()
        
        if action['type'] == 'trim':
            
            return action['original_data']
        
        return None
    
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0
    
    def clear_undo_stack(self):
        self.undo_stack.clear()
    
    def _confirm_trim(
        self, 
        duration_before: int, 
        duration_after: int,
        trim_start: int,
        trim_end: int,
        frame_rate: float
    ) -> bool:
        """
        Show confirmation dialog for trim operation.
        
        Returns:
            True if user confirmed, False otherwise
        """
        removed_frames = duration_before - duration_after
        time_before = duration_before / frame_rate
        time_after = duration_after / frame_rate
        
        message = (
            f"Trim recording?\n\n"
            f"Original: {duration_before} frames ({time_before:.2f}s)\n"
            f"Trimmed: {duration_after} frames ({time_after:.2f}s)\n\n"
            f"Remove {removed_frames} frames?\n\n"
            f"This will:\n"
        )
        

        if trim_start > 0:
            message += f"• Cut frames 0-{trim_start-1} from start ({trim_start} frames)\n"
        
        if trim_end < duration_before - 1:
            end_removed = duration_before - trim_end - 1
            message += f"• Cut frames {trim_end+1}-{duration_before-1} from end ({end_removed} frames)\n"
        
        message += f"• Keep frames {trim_start}-{trim_end}\n\n"
        message += "You can undo this action (Ctrl+Z)."
        
        parent = self.parent_widget if self.parent_widget else None


        dlg = styled_message_box(
            QMessageBox.Question,
            "Apply Trim",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
            parent=parent
        )
        clicked = dlg.standardButton(dlg.clickedButton()) if hasattr(dlg, 'clickedButton') else QMessageBox.No
        return clicked == QMessageBox.Yes
    
    def _show_success(self, duration_after: int, frame_rate: float):
        time_after = duration_after / frame_rate
        
        message = (
            f"Recording trimmed successfully!\n\n"
            f"New duration: {duration_after} frames ({time_after:.2f}s)"
        )
        
        parent = self.parent_widget if self.parent_widget else None


        styled_message_box(
            QMessageBox.Information,
            "Trim Applied",
            message,
            parent=parent
        )
    
    @staticmethod
    def validate_trim_range(
        frames_data: np.ndarray, 
        trim_start: int, 
        trim_end: int
    ) -> Tuple[bool, str]:
        """
        Validate trim range.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if frames_data is None or frames_data.shape[0] == 0:
            return False, "No data to trim"
        
        if trim_start < 0 or trim_start >= frames_data.shape[0]:
            return False, f"Invalid start frame: {trim_start}"
        
        if trim_end < 0 or trim_end >= frames_data.shape[0]:
            return False, f"Invalid end frame: {trim_end}"
        
        if trim_start > trim_end:
            return False, f"Start frame ({trim_start}) must be <= end frame ({trim_end})"
        
        if trim_end - trim_start < 1:
            return False, "Trimmed range must contain at least 2 frames"
        
        return True, ""
    
    @staticmethod
    def calculate_trim_info(
        frames_data: np.ndarray,
        trim_start: int,
        trim_end: int,
        frame_rate: float
    ) -> dict:
        """
        Calculate trim information for display.
        
        Returns:
            Dictionary with trim statistics
        """
        if frames_data is None:
            return {}
        
        duration_before = frames_data.shape[0]
        duration_after = trim_end - trim_start + 1
        removed_frames = duration_before - duration_after
        
        return {
            'duration_before': duration_before,
            'duration_after': duration_after,
            'removed_frames': removed_frames,
            'time_before': duration_before / frame_rate,
            'time_after': duration_after / frame_rate,
            'time_removed': removed_frames / frame_rate,
            'trim_start': trim_start,
            'trim_end': trim_end,
            'removed_start': trim_start,
            'removed_end': duration_before - trim_end - 1
        }