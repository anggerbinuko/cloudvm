import React, { useState } from 'react';
import { Button, Dialog, DialogTitle, DialogContent, IconButton } from '@mui/material';
import { Terminal as TerminalIcon } from '@mui/icons-material';
import { Close as CloseIcon } from '@mui/icons-material';
import SSHTerminal from './Terminal';

interface SSHButtonProps {
  vmId: number;
  vmName: string;
  isRunning: boolean;
}

export const SSHButton: React.FC<SSHButtonProps> = ({ vmId, vmName, isRunning }) => {
  const [terminalOpen, setTerminalOpen] = useState(false);

  const handleOpenTerminal = () => {
    setTerminalOpen(true);
  };

  const handleCloseTerminal = () => {
    setTerminalOpen(false);
  };

  return (
    <>
      <Button
        startIcon={<TerminalIcon />}
        onClick={handleOpenTerminal}
        disabled={!isRunning}
        variant="outlined"
        size="small"
        sx={{
          backgroundColor: 'white',
          '&:hover': {
            backgroundColor: '#f5f5f5'
          }
        }}
      >
        SSH
      </Button>

      <Dialog 
        open={terminalOpen} 
        onClose={handleCloseTerminal}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: '8px',
            backgroundColor: '#202124'
          }
        }}
      >
        <DialogTitle sx={{ 
          color: 'white', 
          backgroundColor: '#202124',
          borderBottom: '1px solid #5f6368',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 16px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TerminalIcon sx={{ color: '#8ab4f8' }} />
            <span>SSH-in-browser</span>
          </div>
          <IconButton
            onClick={handleCloseTerminal}
            size="small"
            sx={{ color: 'white' }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ 
          backgroundColor: '#202124', 
          padding: '16px',
          minHeight: '400px'
        }}>
          {terminalOpen && (
            <SSHTerminal 
              vmId={vmId}
              apiBaseUrl={process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1'}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default SSHButton;
