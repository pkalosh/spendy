/**
 * Spendy - Custom Scripts
 * All JavaScript functionality for the Spendy expense management application
 */

(function() {
    'use strict';
    
    // Document Ready Function
    document.addEventListener('DOMContentLoaded', function() {
      // Initialize all components
      initNavbar();
      initScrollToTop();
      initDropdowns();
      initAlerts();
      initFormValidation();
      initDashboardCharts();
    });
  
    /**
     * Initialize mobile navbar functionality
     */
    function initNavbar() {
      const navbarToggler = document.querySelector('.navbar-toggler');
      const navbarCollapse = document.querySelector('.navbar-collapse');
      
      if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', function() {
          navbarCollapse.classList.toggle('show');
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(event) {
          if (!event.target.closest('.navbar') && navbarCollapse.classList.contains('show')) {
            navbarCollapse.classList.remove('show');
          }
        });
      }
      
      // Handle dropdowns in mobile view
      const dropdownToggle = document.querySelectorAll('.dropdown-toggle');
      dropdownToggle.forEach(function(toggle) {
        toggle.addEventListener('click', function(e) {
          if (window.innerWidth < 992) {
            e.preventDefault();
            const parent = this.parentNode;
            const dropdown = parent.querySelector('.dropdown-menu');
            
            if (dropdown) {
              dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
            }
          }
        });
      });
    }
    
    /**
     * Initialize scroll to top functionality
     */
    function initScrollToTop() {
      const scrollBtn = document.querySelector('.scrollToTop');
      
      if (scrollBtn) {
        window.addEventListener('scroll', function() {
          if (window.pageYOffset > 300) {
            scrollBtn.classList.add('active');
          } else {
            scrollBtn.classList.remove('active');
          }
        });
        
        scrollBtn.addEventListener('click', function() {
          window.scrollTo({
            top: 0,
            behavior: 'smooth'
          });
        });
      }
    }
    
    /**
     * Initialize dropdown functionality
     */
    function initDropdowns() {
      const dropdowns = document.querySelectorAll('.main-navbar');
      
      dropdowns.forEach(function(dropdown) {
        const link = dropdown.querySelector('.nav-link');
        const menu = dropdown.querySelector('.dropdown-menu');
        
        if (link && menu && window.innerWidth >= 992) {
          // Desktop dropdown hover
          dropdown.addEventListener('mouseenter', function() {
            menu.style.display = 'block';
          });
          
          dropdown.addEventListener('mouseleave', function() {
            menu.style.display = 'none';
          });
        }
      });
    }
    
    /**
     * Initialize alerts auto-dismiss
     */
    function initAlerts() {
      const alerts = document.querySelectorAll('.alert');
      
      if (alerts.length > 0) {
        alerts.forEach(function(alert) {
          setTimeout(function() {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s';
            
            setTimeout(function() {
              if (alert.parentNode) {
                alert.parentNode.removeChild(alert);
              }
            }, 500);
          }, 4000);
        });
      }
    }
    
    /**
     * Initialize form validation
     */
    function initFormValidation() {
      const forms = document.querySelectorAll('form');
      
      forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
          if (!form.checkValidity()) {
            event.preventDefault();
            event.stopPropagation();
            highlightInvalidFields(form);
          }
        });
        
        // Add focus effects to input fields
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(function(input) {
          // Focus effect
          input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
          });
          
          // Blur effect
          input.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
            
            // Add 'filled' class if input has value
            if (this.value.trim() !== '') {
              this.parentElement.classList.add('filled');
            } else {
              this.parentElement.classList.remove('filled');
            }
          });
          
          // Initialize filled state
          if (input.value.trim() !== '') {
            input.parentElement.classList.add('filled');
          }
        });
      });
    }
    
    /**
     * Highlight invalid form fields
     * @param {HTMLFormElement} form - The form to validate
     */
    function highlightInvalidFields(form) {
      const invalidInputs = form.querySelectorAll(':invalid');
      
      invalidInputs.forEach(function(input) {
        input.parentElement.classList.add('is-invalid');
        
        // Add error message if not exists
        let errorMsg = input.parentElement.querySelector('.error-message');
        if (!errorMsg) {
          errorMsg = document.createElement('div');
          errorMsg.className = 'error-message';
          errorMsg.style.color = '#FF4D4F';
          errorMsg.style.fontSize = '12px';
          errorMsg.style.marginTop = '5px';
          
          // Customize error message based on validation state
          if (input.validity.valueMissing) {
            errorMsg.textContent = 'This field is required';
          } else if (input.validity.typeMismatch) {
            errorMsg.textContent = 'Please enter a valid format';
          } else if (input.validity.patternMismatch) {
            errorMsg.textContent = 'Please match the requested format';
          }
          
          input.parentElement.appendChild(errorMsg);
        }
        
        // Remove error when input changes
        input.addEventListener('input', function() {
          if (this.validity.valid) {
            this.parentElement.classList.remove('is-invalid');
            if (errorMsg) {
              errorMsg.remove();
            }
          }
        });
      });
    }
  
    /**
     * Initialize dashboard charts (if on dashboard page)
     */
    function initDashboardCharts() {
      // Check if we're on the dashboard page
      const dashboardCharts = document.querySelector('#expense-chart');
      
      if (dashboardCharts) {
        // Implement chart functionality here
        // This would typically use Chart.js or a similar library
        console.log('Dashboard charts would initialize here');
        
        // Example placeholder for chart initialization code that would 
        // be implemented when the required libraries are included
      }
    }
    
    /**
     * Format currency values
     * @param {number} value - The number to format
     * @param {string} currency - Currency code (default: USD)
     * @return {string} Formatted currency string
     */
    window.formatCurrency = function(value, currency = 'USD') {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
      }).format(value);
    };
    
    /**
     * Format date values
     * @param {Date|string} date - Date object or string
     * @param {string} format - Format style (default: 'medium')
     * @return {string} Formatted date string
     */
    window.formatDate = function(date, format = 'medium') {
      const dateObj = new Date(date);
      
      const options = {
        short: { month: 'numeric', day: 'numeric', year: '2-digit' },
        medium: { month: 'short', day: 'numeric', year: 'numeric' },
        long: { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }
      };
      
      return new Intl.DateTimeFormat('en-US', options[format]).format(dateObj);
    };
    
  })();