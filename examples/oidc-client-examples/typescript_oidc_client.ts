/**
 * TypeScript OIDC Client Example for API Forge
 *
 * This example demonstrates how to authenticate with an API Forge backend using OIDC.
 * It handles the authorization code flow with PKCE for secure authentication.
 *
 * Dependencies:
 *   npm install axios
 *   npm install --save-dev @types/node
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import * as crypto from 'crypto';

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  scope?: string;
}

interface UserInfo {
  sub: string;
  email?: string;
  name?: string;
  picture?: string;
  [key: string]: any;
}

interface PKCEPair {
  verifier: string;
  challenge: string;
}

/**
 * OIDC client for authenticating with API Forge backend.
 *
 * This client implements the Authorization Code Flow with PKCE (Proof Key for Code Exchange)
 * for secure authentication without exposing client secrets.
 */
export class APIForgeClient {
  private apiBaseUrl: string;
  private clientId: string;
  private redirectUri: string;
  private provider: string;
  private httpClient: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  /**
   * Initialize the API Forge client.
   *
   * @param apiBaseUrl - Base URL of your API Forge backend (e.g., "https://api.example.com")
   * @param clientId - OAuth client ID from your OIDC provider
   * @param redirectUri - Redirect URI registered with your OIDC provider
   * @param provider - OIDC provider name ("google", "microsoft", or "keycloak")
   */
  constructor(
    apiBaseUrl: string,
    clientId: string,
    redirectUri: string = 'http://localhost:3000/callback',
    provider: string = 'google'
  ) {
    this.apiBaseUrl = apiBaseUrl.replace(/\/$/, '');
    this.clientId = clientId;
    this.redirectUri = redirectUri;
    this.provider = provider;
    this.httpClient = axios.create({
      baseURL: this.apiBaseUrl,
      withCredentials: true,
    });
  }

  /**
   * Generate PKCE code verifier and challenge.
   */
  private generatePKCEPair(): PKCEPair {
    // Generate code verifier (43-128 characters)
    const verifier = crypto
      .randomBytes(32)
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');

    // Generate code challenge (SHA256 hash of verifier)
    const challenge = crypto
      .createHash('sha256')
      .update(verifier)
      .digest('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');

    return { verifier, challenge };
  }

  /**
   * Generate a random state parameter for CSRF protection.
   */
  private generateState(): string {
    return crypto.randomBytes(32).toString('base64url');
  }

  /**
   * Get the authorization URL to redirect the user to.
   *
   * @returns Object containing the authorization URL and code verifier.
   *          Store the code_verifier securely - you'll need it to exchange the code for tokens.
   */
  getAuthorizationUrl(): { authUrl: string; codeVerifier: string; state: string } {
    const { verifier, challenge } = this.generatePKCEPair();
    const state = this.generateState();

    const params = new URLSearchParams({
      client_id: this.clientId,
      response_type: 'code',
      redirect_uri: this.redirectUri,
      scope: 'openid profile email',
      state: state,
      code_challenge: challenge,
      code_challenge_method: 'S256',
    });

    const authUrl = `${this.apiBaseUrl}/auth/web/login?provider=${this.provider}&${params.toString()}`;

    return { authUrl, codeVerifier: verifier, state };
  }

  /**
   * Exchange authorization code for access and refresh tokens.
   *
   * @param code - Authorization code from the callback
   * @param codeVerifier - PKCE code verifier from getAuthorizationUrl()
   * @returns Token response containing access_token, refresh_token, and metadata
   */
  async exchangeCodeForTokens(code: string, codeVerifier: string): Promise<TokenResponse> {
    const data = new URLSearchParams({
      grant_type: 'authorization_code',
      code: code,
      redirect_uri: this.redirectUri,
      client_id: this.clientId,
      code_verifier: codeVerifier,
    });

    const response = await this.httpClient.post<TokenResponse>(
      '/auth/web/token',
      data.toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    this.accessToken = response.data.access_token;
    this.refreshToken = response.data.refresh_token || null;

    return response.data;
  }

  /**
   * Refresh the access token using the refresh token.
   *
   * @returns Token response containing new access_token and metadata
   */
  async refreshAccessToken(): Promise<TokenResponse> {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    const data = new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: this.refreshToken,
      client_id: this.clientId,
    });

    const response = await this.httpClient.post<TokenResponse>(
      '/auth/web/token',
      data.toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    this.accessToken = response.data.access_token;
    if (response.data.refresh_token) {
      this.refreshToken = response.data.refresh_token;
    }

    return response.data;
  }

  /**
   * Get user information from the /auth/me endpoint.
   *
   * @returns User information (email, name, etc.)
   */
  async getUserInfo(): Promise<UserInfo> {
    if (!this.accessToken) {
      throw new Error('No access token available. Please authenticate first.');
    }

    const response = await this.httpClient.get<UserInfo>('/auth/me', {
      headers: {
        Authorization: `Bearer ${this.accessToken}`,
      },
    });

    return response.data;
  }

  /**
   * Make an authenticated API request.
   *
   * @param method - HTTP method (GET, POST, PUT, DELETE, etc.)
   * @param endpoint - API endpoint (e.g., "/api/users")
   * @param config - Additional axios configuration
   * @returns Axios response
   */
  async makeAuthenticatedRequest<T = any>(
    method: string,
    endpoint: string,
    config?: AxiosRequestConfig
  ): Promise<AxiosResponse<T>> {
    if (!this.accessToken) {
      throw new Error('No access token available. Please authenticate first.');
    }

    const headers = {
      ...config?.headers,
      Authorization: `Bearer ${this.accessToken}`,
    };

    try {
      return await this.httpClient.request<T>({
        method,
        url: endpoint,
        ...config,
        headers,
      });
    } catch (error: any) {
      // Try to refresh token if we get 401
      if (error.response?.status === 401 && this.refreshToken) {
        try {
          await this.refreshAccessToken();
          headers.Authorization = `Bearer ${this.accessToken}`;
          return await this.httpClient.request<T>({
            method,
            url: endpoint,
            ...config,
            headers,
          });
        } catch (refreshError) {
          // Let the original 401 bubble up
          throw error;
        }
      }
      throw error;
    }
  }

  /**
   * Logout and clear tokens.
   */
  async logout(): Promise<void> {
    if (this.accessToken) {
      try {
        await this.httpClient.post('/auth/web/logout', null, {
          headers: {
            Authorization: `Bearer ${this.accessToken}`,
          },
        });
      } catch (error) {
        // Ignore errors during logout
      }
    }

    this.accessToken = null;
    this.refreshToken = null;
  }

  /**
   * Get the current access token.
   */
  getAccessToken(): string | null {
    return this.accessToken;
  }

  /**
   * Set the access token manually (e.g., from storage).
   */
  setAccessToken(token: string): void {
    this.accessToken = token;
  }

  /**
   * Get the current refresh token.
   */
  getRefreshToken(): string | null {
    return this.refreshToken;
  }

  /**
   * Set the refresh token manually (e.g., from storage).
   */
  setRefreshToken(token: string): void {
    this.refreshToken = token;
  }
}

// Example usage for Node.js
async function exampleUsage() {
  const client = new APIForgeClient(
    'http://localhost:8000',
    'your-client-id',
    'http://localhost:3000/callback',
    'google'
  );

  // Step 1: Get authorization URL
  const { authUrl, codeVerifier, state } = client.getAuthorizationUrl();
  console.log('🔐 Authorization URL:', authUrl);
  console.log('📝 Store code_verifier and state securely');

  // Step 2: User visits authUrl and gets redirected back with code
  // In a real app, you'd extract this from the callback URL
  const authorizationCode = 'code-from-callback';

  try {
    // Step 3: Exchange code for tokens
    const tokens = await client.exchangeCodeForTokens(authorizationCode, codeVerifier);
    console.log('✅ Access Token:', tokens.access_token.substring(0, 50) + '...');

    // Step 4: Get user info
    const userInfo = await client.getUserInfo();
    console.log('👤 User:', userInfo.email);

    // Step 5: Make authenticated API requests
    const response = await client.makeAuthenticatedRequest('GET', '/api/health');
    console.log('📡 API Health Check:', response.status);

    // Step 6: Refresh token when needed
    if (client.getRefreshToken()) {
      const newTokens = await client.refreshAccessToken();
      console.log('🔄 Token refreshed');
    }

    // Step 7: Logout
    await client.logout();
    console.log('👋 Logged out');
  } catch (error) {
    console.error('❌ Error:', error);
  }
}

// Uncomment to run the example
// exampleUsage();

export default APIForgeClient;
