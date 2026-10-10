import { createTheme } from '@mui/material/styles';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00f2fe', // Electric cyan/teal
      light: '#70f3ff',
      dark: '#00a3ae',
    },
    secondary: {
      main: '#9d4edd', // Neon purple/violet
      light: '#c77dff',
      dark: '#7b2cbf',
    },
    background: {
      default: '#070a13', // Deep slate space background
      paper: 'rgba(15, 22, 42, 0.75)', // Transparent glass effect
    },
    text: {
      primary: '#f8fafc',
      secondary: '#94a3b8',
    },
    error: {
      main: '#f43f5e', // Vibrant rose red
    },
    warning: {
      main: '#f59e0b', // Amber
    },
    success: {
      main: '#10b981', // Emerald green
    },
    info: {
      main: '#0ea5e9', // Sky blue
    },
  },
  typography: {
    fontFamily: '"Inter", "Outfit", "Helvetica", "Arial", sans-serif',
    h1: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 800,
    },
    h2: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 700,
    },
    h3: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 600,
    },
    h4: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 600,
    },
    h5: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 500,
    },
    h6: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 500,
    },
    button: {
      textTransform: 'none',
      fontWeight: 600,
    },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: 'rgba(15, 22, 42, 0.6)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: 16,
          boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backdropFilter: 'blur(4px)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
  },
});

export default darkTheme;
