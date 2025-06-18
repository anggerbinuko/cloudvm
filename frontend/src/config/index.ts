const config = {
    API_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1',
    APP_NAME: 'VM Management System',
    TOKEN_KEY: 'vm_mgmt_token',
  };
  
  export const { API_URL, APP_NAME, TOKEN_KEY } = config;
  
  export default config;