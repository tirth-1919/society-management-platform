/**
 * razorpay_checkout.js
 *
 * Reusable Razorpay Checkout initialization module.
 *
 * SECURITY RULES:
 * - This file NEVER stores or logs the Razorpay Key Secret.
 * - Payment success is NEVER decided here — only the server verification endpoint
 *   decides whether a payment is captured.
 * - Double-submission is prevented by the `submitted` guard flag.
 * - If verification fails, the user sees a clear error and can retry.
 */

'use strict';

/**
 * initRazorpayCheckout — launches Razorpay Checkout for a single bill or multi-month order.
 *
 * @param {Object} opts
 * @param {number} opts.billId          - Bill ID (for single bill)
 * @param {string} opts.createOrderUrl  - Server endpoint to create Razorpay order
 * @param {string} opts.verifyUrl       - Server endpoint to verify payment
 * @param {string} opts.failedUrl       - Redirect URL on payment failure
 * @param {string} opts.cancelledUrl    - Redirect URL on checkout cancellation
 * @param {HTMLElement} opts.payBtn     - The Pay Now button element
 * @param {HTMLElement} opts.processingEl - Processing spinner element
 * @param {HTMLElement} opts.errorEl    - Error banner element
 * @param {HTMLElement} opts.errorMsgEl - Error message span element
 * @param {Array} [opts.billIds]        - List of bill IDs for multi-month orders
 * @param {string} [opts.multiOrderUrl] - Server endpoint for multi-month orders
 */
function initRazorpayCheckout(opts) {
  // Prevent double-click
  if (opts.payBtn._rzpSubmitted) return;
  opts.payBtn._rzpSubmitted = true;
  opts.payBtn.disabled = true;
  opts.payBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Preparing checkout…';

  if (opts.errorEl) opts.errorEl.style.display = 'none';

  // Determine if this is a multi-month or single bill order
  const isMulti = Array.isArray(opts.billIds) && opts.billIds.length > 0;
  const orderUrl = isMulti ? (opts.multiOrderUrl || opts.createOrderUrl) : opts.createOrderUrl;
  const body = isMulti
    ? JSON.stringify({ bill_ids: opts.billIds })
    : JSON.stringify({ bill_id: opts.billId });

  // Step 1: Create order on server
  fetch(orderUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: body,
  })
    .then(function(res) {
      if (!res.ok) {
        return res.json().then(function(d) {
          throw new Error(d.error || 'Order creation failed. Please try again.');
        });
      }
      return res.json();
    })
    .then(function(orderData) {
      // Step 2: Launch Razorpay Checkout modal
      const options = {
        key: orderData.key_id,           // Public key only — secret never sent here
        amount: orderData.amount_paise,  // Amount in paise
        currency: orderData.currency || 'INR',
        order_id: orderData.order_id,
        name: orderData.society_name || 'Society Maintenance',
        description: isMulti
          ? 'Multi-Month Maintenance Payment'
          : 'Monthly Maintenance Payment',
        prefill: {
          name: orderData.resident_name || '',
        },
        theme: {
          color: '#4F46E5',
        },
        modal: {
          ondismiss: function() {
            // User closed checkout without paying — reset button, redirect to cancelled
            opts.payBtn._rzpSubmitted = false;
            opts.payBtn.disabled = false;
            opts.payBtn.innerHTML = '<i class="fa-solid fa-credit-card"></i> Pay Now';
            if (opts.cancelledUrl) {
              window.location.href = opts.cancelledUrl;
            }
          },
        },
        handler: function(response) {
          // Step 3: Payment submitted by Razorpay — VERIFY on server before marking paid
          _verifyPayment(response, orderData, opts);
        },
      };

      const rzp = new Razorpay(options);

      rzp.on('payment.failed', function(response) {
        const errMsg = (response.error && response.error.description) || 'Payment failed.';
        _showError(opts, errMsg);
        opts.payBtn._rzpSubmitted = false;
        opts.payBtn.disabled = false;
        opts.payBtn.innerHTML = '<i class="fa-solid fa-credit-card"></i> Retry Payment';
        if (opts.failedUrl) {
          setTimeout(function() { window.location.href = opts.failedUrl; }, 2000);
        }
      });

      rzp.open();
    })
    .catch(function(err) {
      _showError(opts, err.message || 'Could not start payment. Please try again.');
      opts.payBtn._rzpSubmitted = false;
      opts.payBtn.disabled = false;
      opts.payBtn.innerHTML = '<i class="fa-solid fa-credit-card"></i> Pay Now';
    });
}

/**
 * _verifyPayment — sends Razorpay response to server for HMAC verification.
 * The server is the ONLY authority that decides payment success.
 */
function _verifyPayment(response, orderData, opts) {
  if (opts.processingEl) opts.processingEl.style.display = 'block';
  if (opts.payBtn) opts.payBtn.style.display = 'none';

  fetch(opts.verifyUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({
      razorpay_order_id: response.razorpay_order_id,
      razorpay_payment_id: response.razorpay_payment_id,
      razorpay_signature: response.razorpay_signature,
    }),
  })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.success && data.redirect_url) {
        // Server confirmed — redirect to success page
        window.location.href = data.redirect_url;
      } else {
        _showError(opts, data.error || 'Payment verification failed. Please contact support.');
        if (opts.processingEl) opts.processingEl.style.display = 'none';
        if (opts.payBtn) {
          opts.payBtn.style.display = '';
          opts.payBtn._rzpSubmitted = false;
          opts.payBtn.disabled = false;
          opts.payBtn.innerHTML = '<i class="fa-solid fa-credit-card"></i> Retry Payment';
        }
      }
    })
    .catch(function() {
      _showError(opts, 'Verification request failed. If money was deducted, please contact support.');
      if (opts.processingEl) opts.processingEl.style.display = 'none';
      if (opts.payBtn) {
        opts.payBtn.style.display = '';
        opts.payBtn._rzpSubmitted = false;
        opts.payBtn.disabled = false;
      }
    });
}

function _showError(opts, msg) {
  if (opts.errorEl && opts.errorMsgEl) {
    opts.errorMsgEl.textContent = msg;
    opts.errorEl.style.display = 'block';
  } else {
    console.error('[Razorpay]', msg);
  }
}
