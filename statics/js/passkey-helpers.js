'use strict';

const Passkey = {};

(function () {
  const base64url = (() => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    // Use a lookup table to find the index.
    const lookup = new Uint8Array(256);
    for (let idx = chars.length - 1; idx >= 0; idx--) {
      lookup[chars.charCodeAt(idx)] = idx;
    }

    const encode = (buf) => {
      const bytes = new Uint8Array(buf);
      const len = bytes.length;
      let base64string = '';

      for (let idx = 0; idx < len; idx += 3) {
        const idx0 = idx;
        const idx1 = idx + 1;
        const idx2 = idx + 2;
        base64string += chars[bytes[idx0] >> 2];
        base64string += chars[((bytes[idx0] & 0x03) << 4) | (bytes[idx1] >> 4)];
        base64string += chars[((bytes[idx1] & 0x0F) << 2) | (bytes[idx2] >> 6)];
        base64string += chars[bytes[idx2] & 0x3F];
      }

      if ((len % 3) === 2) {
        base64string = base64string.substring(0, base64string.length - 1);
      }
      else if (len % 3 === 1) {
        base64string = base64string.substring(0, base64string.length - 2);
      }

      return base64string;
    };
    const decode = (base64string) => {
      const len = base64string.length;
      const bufLen = len * 0.75;
      const bytes = new Uint8Array(bufLen);
      let pos = 0;

      for (let idx = 0; idx < len; idx += 4) {
        const encoded1 = lookup[base64string.charCodeAt(idx)];
        const encoded2 = lookup[base64string.charCodeAt(idx + 1)];
        const encoded3 = lookup[base64string.charCodeAt(idx + 2)];
        const encoded4 = lookup[base64string.charCodeAt(idx + 3)];
        bytes[pos++] = (encoded1 << 2) | (encoded2 >> 4);
        bytes[pos++] = ((encoded2 & 0x0F) << 4) | (encoded3 >> 2);
        bytes[pos++] = ((encoded3 & 0x03) << 6) | (encoded4 & 0x3F);
      }

      return bytes.buffer;
    };

    const methods = {
      'encode': encode,
      'decode': decode,
    };

    return methods;
  })();

  const publickeyCredentialToJson = (publicKeyCred) => {
    const convertClientExtension = (extension) => {
      const obj = {};

      for (const key of Object.keys(extension)) {
        obj[key] = base64url.encode(extension[key]);
      }

      return obj;
    };
    const convertResponse = (response) => {
      const convertArrayToJSON = (arr) => Object.fromEntries(arr.map((val, idx) => [idx, val]));

      if (response instanceof AuthenticatorAttestationResponse) {
        const obj = {
          attestationObject: base64url.encode(response.attestationObject),
          authenticatorData: base64url.encode(response.getAuthenticatorData()),
          clientDataJSON: base64url.encode(response.clientDataJSON),
          publicKey: base64url.encode(response.getPublicKey()),
          publicKeyAlgorithm: response.getPublicKeyAlgorithm(),
          transports: convertArrayToJSON(response.getTransports()),
        }

        return obj;
      }
      else if (response instanceof AuthenticatorAssertionResponse) {
        const obj = {
          authenticatorData: base64url.encode(response.authenticatorData),
          clientDataJSON: base64url.encode(response.clientDataJSON),
          signature: base64url.encode(response.signature),
          userHandle: base64url.encode(response.userHandle),
        };

        return obj;
      }
      else {
        return undefined;
      }
    };

    //
    // Main routine in publickeyCredentialToJson
    //
    if ('toJSON' in publicKeyCred) {
      return publicKeyCred.toJSON();
    }
    else {
      const obj = {
        authenticatorAttachment: publicKeyCred.authenticatorAttachment || undefined,
        clientExtensionResults: convertClientExtension(publicKeyCred.getClientExtensionResults()),
        id: publicKeyCred.id,
        rawId: base64url.encode(publicKeyCred.rawId),
        response: convertResponse(publicKeyCred.response),
        type: publicKeyCred.type,
      };
      const ret = {};
      // Delete `undefined` element
      for (const key of Object.keys(obj)) {
        if (obj[key]) {
          ret[key] = obj[key];
        }
      }

      return ret;
    }
  };

  const makeCredReq = (credReq) => {
    credReq.publicKey.challenge = base64url.decode(credReq.publicKey.challenge);
    credReq.publicKey.user.id = base64url.decode(credReq.publicKey.user.id);

    for (const excludeCred of credReq.publicKey.excludeCredentials) {
      excludeCred.id = base64url.decode(excludeCred.id);
    }

    return credReq;
  };

  const getAssertReq = (assertReq) => {
    assertReq.publicKey.challenge = base64url.decode(assertReq.publicKey.challenge);

    for (const allowCred of assertReq.publicKey.allowCredentials) {
      allowCred.id = base64url.decode(allowCred.id);
    }

    return assertReq;
  };

  /**
    * @brief Initialization
  */
  Passkey.Init = () => {
    const controller = new AbortController();
    window.conditionalUI = false;
    window.conditionUIAbortController = controller;
    window.conditionUIAbortSignal = controller.signal;
  };

  /**
    * @brief Register passkey
    * @param[in] registerURL URL to register passkey
    * @param[in] completeURL URL to complete passkey registration
    * @param[in] keyName Key name of passkey
    * @param[in] csrftoken CSRF token which is used to complete passkey registration
    * @param[in] callback The callback function after completing passkey registration
  */
  Passkey.RegisterPasskey = (registerURL, completeURL, keyName, csrftoken, callback) => {
    // Register passkey
    fetch(registerURL, { method: 'GET' }).then((response) => {
      // Check response status
      if (!response.ok) {
        throw new Error('Getting registration data!');
      }

      return response.json();
    }).then((data) => {
      const options = makeCredReq(data);
      // Create credential
      return navigator.credentials.create(options);
    }).then((credential) => {
      // Complete passkey registration
      const jsonData = publickeyCredentialToJson(credential);
      jsonData['key_name'] = keyName;

      return fetch(completeURL, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(jsonData),
      });
    }).then((response) => {
      return response.json();
    }).then((data) => {
      // Callback with received data
      callback(data.code, data.message);
    }).catch((err) => {
      const statusCode = err.status_code || 500;
      const message = err.message || err;
      // Callback with error message
      callback(statusCode, message);
    });
  };

  /**
   * @brief Check conditional UI
   * @param[in] callback The callback function after checking whether conditional mediation is available or not
  */
  Passkey.CheckConditionalUI = (callback) => {
    if (window.PublicKeyCredential && PublicKeyCredential.isConditionalMediationAvailable) {
      // Check if conditional mediation is available
      PublicKeyCredential.isConditionalMediationAvailable().then((result) => {
        window.conditionalUI = result;
        callback(true, null);
      }).catch((err) => {
        callback(false, err);
      });
    }
  };

  /**
   * @brief Authenticate account using passkey
   * @param[in] authURL URL to authenticate account using passkey
   * @param[in] formElement Target form to login using passkey
   * @param[in] passkeyElement Target passkey element
   * @param[in] hasConditionalUI Describe whether the system can use conditional UI or not
   * @param[in] callback The callback function if error has occured
  */
  Passkey.Authentication = (authURL, formElement, passkeyElement, hasConditionalUI = false, callback = null) => {
    const failedCallback = callback || ((err) => null);
    // Authentication with passkey
    fetch(authURL, { method: 'GET' }).then((response) => {
      // Check response status
      if (!response.ok) {
        throw new Error('No credential available to authenticate!');
      }

      return response.json();
    }).then((data) => {
      const options = getAssertReq(data);
      // Get credentials
      if (hasConditionalUI) {
        options.mediation = 'conditional';
        options.signal = window.conditionUIAbortSignal;
      }
      else {
        window.conditionUIAbortController.abort('Intended refusal due to not be able to use conditional ui.');
      }

      return navigator.credentials.get(options);
    }).then((assertion) => {
      passkeyElement.value = JSON.stringify(publickeyCredentialToJson(assertion));
      formElement.submit();
    }).catch((err) => {
      failedCallback(err);
    });
  };

  /**
   * @brief Check passkey
   * @param[in] callback The callback function when the user can use passkey authentication
   * @param[in] errHandle The function for error handle
  */
  Passkey.CheckPasskeys = (callback, errHandle = null) => {
    const failedCallback = errHandle || ((err) => null);

    PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable().then((isAvailable) => {
      if (isAvailable) {
        callback();
      }
      else {
        failedCallback('Cannot use passkey on your device.');
      }
    }).catch((err) => {
      failedCallback(err);
    });
  };

  Object.freeze(Passkey);
})();