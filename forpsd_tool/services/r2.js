const fs = require('fs');
const https = require('https');
const crypto = require('crypto');
const config = require('../config');

function hmac(key, data, enc) {
  return crypto.createHmac('sha256', key).update(data).digest(enc || 'buffer');
}

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function uploadBufferToR2(buffer, key, contentType = 'image/webp') {
  return new Promise((resolve, reject) => {
    const { accountId, accessKeyId, secretAccessKey, bucket, cdnBase } = config.R2;

    const now = new Date();
    const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '').slice(0, 15) + 'Z';
    const dateStamp = amzDate.slice(0, 8);
    const host = `${accountId}.r2.cloudflarestorage.com`;
    const uri = `/${bucket}/${key}`;
    const payloadHash = sha256(buffer);

    const headers = {
      'host': host,
      'x-amz-date': amzDate,
      'x-amz-content-sha256': payloadHash,
      'content-type': contentType,
      'content-length': buffer.length.toString(),
      'cache-control': 'public, max-age=31536000, immutable'
    };

    const signedHeaders = Object.keys(headers).sort().join(';');
    const canonicalHeaders = Object.keys(headers).sort().map(k => `${k}:${headers[k]}\n`).join('');
    const canonicalReq = ['PUT', uri, '', canonicalHeaders, signedHeaders, payloadHash].join('\n');
    const credScope = `${dateStamp}/auto/s3/aws4_request`;
    const strToSign = `AWS4-HMAC-SHA256\n${amzDate}\n${credScope}\n${sha256(canonicalReq)}`;
    const sigKey = hmac(hmac(hmac(hmac('AWS4' + secretAccessKey, dateStamp), 'auto'), 's3'), 'aws4_request');
    const signature = hmac(sigKey, strToSign, 'hex');
    const authHeader = `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

    const req = https.request({
      hostname: host,
      path: uri,
      method: 'PUT',
      headers: { ...headers, 'Authorization': authHeader }
    }, res => {
      let body = '';
      res.on('data', d => { body += d; });
      res.on('end', () => {
        if (res.statusCode === 200) {
          const publicUrl = `${cdnBase}/${key}`;
          resolve(publicUrl);
        } else {
          reject(new Error(`R2 Upload HTTP ${res.statusCode}: ${body.slice(0, 200)}`));
        }
      });
    });

    req.on('error', reject);
    req.write(buffer);
    req.end();
  });
}

const postFormatter = require('./post_formatter');

async function uploadWebpToR2(filePath, id) {
  const formattedId = postFormatter.getFormattedDesignId(id);
  const key = `previews/${formattedId}.webp`;
  const fileBuffer = fs.readFileSync(filePath);
  const publicUrl = await uploadBufferToR2(fileBuffer, key, 'image/webp');
  return publicUrl;
}

module.exports = {
  uploadBufferToR2,
  uploadWebpToR2
};
