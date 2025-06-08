# Terms of Service

## 1. Introduction
These Terms of Service ("Terms") govern the use of DataFlow Solutions’ cloud-based business intelligence (BI) and data visualization platform ("Platform"), including its website (app.dataflow.com), mobile app, and APIs (api_documentation.json), by all users ("Users" or "You") for our 5,000+ customers across 40+ countries (customer_analytics.csv). By accessing or using the Platform, You agree to be bound by these Terms, effective as of Your first use or subscription start date (billing_and_pricing.csv). DataFlow Solutions, Inc. ("We," "Us," or "DataFlow"), a Delaware corporation located at 123 Market St, San Francisco, CA 94105, provides the Platform subject to these Terms.

This agreement incorporates our Privacy Policy (privacy_policy.txt), Security Policies (security_policies.txt), and other referenced documents. For support, contact support@dataflow.com or +1-800-555-1234 (customer_support_procedures.md). For legal definitions, see Section 12. These Terms ensure compliance with GDPR, CCPA, HIPAA, and other standards (compliance_certifications.csv).

**Use Case**: Customer 1001 (customer_analytics.csv) agrees to these Terms upon subscribing to the Professional plan ($149/month, billing_and_pricing.csv) for retail analytics (product_user_guide.md, Section 4).
**Edge Case**: Users in the EU (e.g., Customer 1009, customer_analytics.csv) are subject to GDPR-specific clauses (Section 9).

---

## 2. User Rights and Responsibilities
2.1 Rights
You are granted a non-exclusive, non-transferable, revocable license to access and use the Platform per Your subscription plan (Starter, Professional, Enterprise, billing_and_pricing.csv). Rights include:
- Creating dashboards and visualizations (product_user_guide.md, Section 4).
- Connecting data sources (e.g., SQL, APIs, product_user_guide.md, Section 3).
- Using APIs for integrations (api_documentation.json).
- Accessing support per plan SLAs (customer_support_procedures.md, Section 3).

2.2 Responsibilities
You agree to:
- Use the Platform lawfully, per these Terms and applicable laws (compliance_certifications.csv).
- Maintain accurate account information (e.g., email, billing_and_pricing.csv).
- Secure Your account with 2FA (security_policies.txt, Section 1).
- Not share login credentials or bypass security measures (product_user_guide.md, Section 2.2).
- Not reverse-engineer, decompile, or misuse the Platform (api_documentation.json, Security).
- Comply with usage limits (e.g., 1,000 API calls for Starter, billing_and_pricing.csv).

2.3 Prohibited Activities
- Uploading malicious code or unauthorized data (security_policies.txt, Section 4).
- Exceeding plan limits without payment (e.g., API calls, billing_and_pricing.csv).
- Using the Platform for illegal purposes (e.g., fraud, employee_handbook.txt, Section 8).
- Interfering with Platform performance (e.g., DDoS, system_architecture.md).

**Metrics**:
- User Accounts: ~10,000 active (customer_analytics.csv).
- Compliance Violations: <10/year (customer_support_procedures.md).
- Support Tickets for Misuse: ~5/month (Zendesk).

**Edge Case**: Child users (under 16, GDPR) are prohibited without parental consent (privacy_policy.txt, Section 3).
**Use Case**: Customer 1018 (customer_analytics.csv) uses SSO to access dashboards, securing credentials per security_policies.txt.

---

## 3. Subscription and Payment Terms
3.1 Subscription Plans
- **Starter**: $49/month or $470/year, 5 users, 1,000 API calls (billing_and_pricing.csv).
- **Professional**: $149/month or $1430/year, 25 users, 10,000 API calls.
- **Enterprise**: Custom pricing, unlimited users, custom limits (sales_playbook.json).
- Plans auto-renew unless canceled (Section 6).

3.2 Payment Terms
- **Methods**: Credit card, invoice, ACH for Enterprise (billing_and_pricing.csv).
- **Due Date**: Monthly or annually, due on subscription date.
- **Late Fees**: $25–$100 after 30 days, per plan (billing_and_pricing.csv).
- **Refunds**: 30-day money-back guarantee for Starter/Professional; custom for Enterprise (customer_support_procedures.md, Section 6).
- **Overages**: Billed monthly (e.g., $0.01/API call, billing_and_pricing.csv).

3.3 Taxes
- You are responsible for applicable taxes (e.g., VAT for EU, billing_and_pricing.csv).
- US customers: Sales tax per state laws (e.g., 8.5% in California).
- EU customers: VAT included in EUR pricing (e.g., €45/month Starter).

3.4 Metrics
- Subscriptions: ~5,000 active (customer_analytics.csv).
- Late Payments: <2% monthly (Zendesk).
- Refund Requests: ~10/month, 95% within 30 days (customer_support_procedures.md).

**Edge Case**: International customers (e.g., Customer 1009, customer_analytics.csv) pay VAT in GBP/EUR, processed via Stripe (integration_partners.csv).
**Use Case**: Customer 1002 (customer_analytics.csv) subscribes to Starter, paying $470 annually, refunded within 30 days (billing_and_pricing.csv).

---

## 4. Service Availability and Limitations
4.1 Availability
- We target 99.9% uptime (system_architecture.md, Section 7), excluding scheduled maintenance (notified 7 days in advance via status.dataflow.com).
- Outages are managed per incident_response_playbook.txt (e.g., 4-hour RTO for P0).

4.2 Limitations
- Plan-specific limits apply (e.g., 20 dashboards for Starter, billing_and_pricing.csv).
- API rate limits: 1,000–10,000 calls/month (api_documentation.json, Rate Limits).
- Data processing: 500MB CSV uploads for Starter, unlimited for Enterprise (product_user_guide.md, Section 3.3).
- Performance may vary for large datasets (>10M rows, troubleshooting_guide.txt, DB-2003).

4.3 Maintenance
- Scheduled: 2–4 AM PST, monthly, <2 hours downtime.
- Emergency: Immediate for security patches (release_notes.json), notified via email.

4.4 Metrics
- Uptime: 99.92% (2024, system_architecture.md).
- Maintenance Downtime: ~10 hours/year (status.dataflow.com).
- SLA Breaches: <5/year, credited per billing_and_pricing.csv.

**Edge Case**: Force majeure events (e.g., natural disasters) may disrupt service without liability (Section 8).
**Use Case**: Customer 1036 (customer_analytics.csv) experiences a P0 outage (DB-2002, troubleshooting_guide.txt), resolved in 3 hours (incident_response_playbook.txt).

---

## 5. Termination and Suspension
5.1 Termination by You
- Cancel via settings.dataflow.com with 7-day notice (customer_support_procedures.md, Section 6).
- Starter/Professional: 30-day refund if canceled within trial (billing_and_pricing.csv).
- Enterprise: Per contract terms (sales_playbook.json).

5.2 Termination by Us
- For non-payment after 30 days (billing_and_pricing.csv).
- For policy violations (e.g., malicious code, Section 2.3).
- With 30-day notice for service discontinuation (rare, status.dataflow.com).

5.3 Suspension
- Immediate for security threats (e.g., API misuse, security_policies.txt, Section 4).
- Non-payment after 15-day notice (billing_and_pricing.csv).
- Restored within 24 hours post-resolution (customer_support_procedures.md).

5.4 Post-Termination
- Data deletion within 90 days (privacy_policy.txt, Section 5).
- Export data within 7 days (product_user_guide.md, Section 6.1).
- Return to trial terms if applicable (terms_of_service.md).

5.5 Metrics
- Terminations: ~50/month (2% churn, customer_analytics.csv).
- Suspensions: ~10/month, 90% resolved <48 hours.
- Data Exports: ~20/month (Zendesk).

**Edge Case**: Enterprise customers (Customer 1033, customer_analytics.csv) with 2-year contracts require 90-day notice for termination (sales_playbook.json).
**Use Case**: Customer 1002 (customer_analytics.csv) cancels Starter plan, exporting dashboards within 5 days (privacy_policy.txt).

---

## 6. Intellectual Property
6.1 Ownership
- **Our Property**: Platform, APIs, documentation, and trademarks (e.g., DataFlow logo) are owned by DataFlow Solutions (product_user_guide.md, api_documentation.json).
- **Your Property**: Data uploaded (e.g., dashboards, data sources) remains Yours (privacy_policy.txt, Section 2).

6.2 License
- We grant You a license to use our IP per Your plan (Section 2.1).
- You grant Us a non-exclusive license to process Your data for service delivery (e.g., analytics, customer_analytics.csv).

6.3 Restrictions
- No modification or distribution of our IP without consent.
- No use of Your data beyond service delivery (privacy_policy.txt, Section 7).

6.4 Metrics
- IP Disputes: <2/year (Zendesk).
- License Audits: Annual, 100% compliance (compliance_certifications.csv).

**Edge Case**: White-labeled dashboards (Customer 1033, customer_analytics.csv) require custom branding approval (billing_and_pricing.csv).
**Use Case**: Customer 1001’s sales dashboards (customer_analytics.csv) remain their property, processed per privacy_policy.txt.

---

## 7. Liability and Warranties
7.1 Warranties
- We warrant the Platform will perform substantially as described (product_user_guide.md).
- No warranty for third-party services (e.g., Salesforce, integration_partners.csv).
- Service provided “as is” without implied warranties (e.g., fitness for purpose).

7.2 Liability Limitations
- Our liability is limited to subscription fees paid in the prior 12 months (billing_and_pricing.csv).
- No liability for indirect damages (e.g., lost profits, data loss).
- You are responsible for data backups (system_architecture.md, Section 8).

7.3 Indemnification
- You indemnify Us against claims from Your data misuse (e.g., illegal uploads, Section 2.3).
- We indemnify You against IP infringement claims for our Platform.

7.4 Metrics
- Liability Claims: <3/year (Zendesk).
- Indemnification Cases: <1/year (legal@dataflow.com).
- Data Loss Incidents: <2/year, all recovered <4 hours (incident_response_playbook.txt).

**Edge Case**: Force majeure (e.g., cyberattacks) limits liability unless negligence proven (security_policies.txt).
**Use Case**: Customer 1015 (customer_analytics.csv) experiences data loss, recovered in 3 hours without liability (system_architecture.md).

---

## 8. Dispute Resolution
8.1 Informal Resolution
- Contact support@dataflow.com within 30 days of issue (customer_support_procedures.md).
- Resolve within 14 days via negotiation.

8.2 Arbitration
- Disputes unresolved informally go to binding arbitration in San Francisco, CA (American Arbitration Association).
- You waive class action rights.
- Costs split per AAA rules, unless We cover for Starter/Professional (billing_and_pricing.csv).

8.3 Exceptions
- IP disputes may go to federal court (San Francisco).
- Injunctive relief for breaches (e.g., data misuse) bypasses arbitration.

8.4 Metrics
- Disputes: ~5/month, 90% resolved informally (Zendesk).
- Arbitrations: <1/year, all settled <6 months.
- Court Cases: 0 in 2024 (legal@dataflow.com).

**Edge Case**: EU customers (Customer 1009, customer_analytics.csv) may arbitrate in London per GDPR (compliance_certifications.csv).
**Use Case**: Customer 1008 (customer_analytics.csv) disputes a late fee, resolved informally in 10 days (customer_support_procedures.md).

---

## 9. Compliance with Laws
9.1 General Compliance
- We comply with GDPR, CCPA, HIPAA, and PCI DSS (compliance_certifications.csv).
- You comply with applicable laws (e.g., anti-spam, employee_handbook.txt, Section 8).

9.2 GDPR/CCPA
- Data protection per privacy_policy.txt (e.g., 30-day erasure).
- EU/UK data stored in Frankfurt (system_architecture.md, Section 8).

9.3 HIPAA
- Enterprise healthcare customers (Customer 1039, customer_analytics.csv) sign BAAs (compliance_certifications.csv).
- Dedicated schemas enforced (system_architecture.md, Section 2).

9.4 Metrics
- Compliance Audits: 100% pass rate (compliance_certifications.csv).
- Regulatory Fines: 0 in 2024 (legal@dataflow.com).
- Customer Audits: ~10/year, all passed (billing_and_pricing.csv).

**Edge Case**: Child data under COPPA (US) requires parental consent (privacy_policy.txt, Section 3).
**Use Case**: Customer 1018 (customer_analytics.csv) signs a HIPAA BAA, ensuring compliance for patient data (release_notes.json, v2.5.0).

---

## 10. Third-Party Services
The Platform integrates with third-party services (e.g., Salesforce, integration_partners.csv), subject to their terms.

10.1 Responsibilities
- You manage third-party credentials (e.g., Salesforce API key, product_user_guide.md, Section 3.2).
- We are not liable for third-party failures (e.g., Google Drive outage, troubleshooting_guide.txt, INT-7002).
- Data shared with vendors is encrypted (security_policies.txt, Section 7).

10.2 Compliance
- Vendors meet SOC 2/ISO 27001 (integration_partners.csv, security_policies.txt, Section 6).
- You ensure third-party compliance with Your data (e.g., GDPR, privacy_policy.txt).

10.3 Metrics
- Third-Party Incidents: <5/year (security_policies.txt).
- Vendor Audits: 30/year, 95% compliance (compliance_certifications.csv).
- Integration Errors: ~50/month (troubleshooting_guide.txt).

**Edge Case**: Vendor breaches (e.g., Salesforce, Customer 1001, customer_analytics.csv) trigger notification within 24 hours (incident_response_playbook.txt).
**Use Case**: Customer 1015 (customer_analytics.csv) integrates Google Drive, managing OAuth per integration_partners.csv.

---

## 11. Updates to Terms
We may update these Terms to reflect legal, technical, or operational changes.

11.1 Process
- Review annually or upon major changes (e.g., v2.5.0, release_notes.json).
- Notify via email and app.dataflow.com (30-day notice).
- Continued use post-update implies acceptance.
- Archive prior versions at terms.dataflow.com.

11.2 Metrics
- Updates: 2/year (e.g., GDPR, HIPAA, compliance_certifications.csv).
- Notifications: 100% within 30 days (status.dataflow.com).
- Queries Post-Update: <10/month (Zendesk).

**Edge Case**: Emergency updates (e.g., new law) are effective immediately with 7-day notice.
**Use Case**: v2.5.0’s HIPAA terms (release_notes.json) were emailed to Customer 1039 (customer_analytics.csv), accepted via continued use.

---

## 12. Governing Law and Contact
12.1 Governing Law
- US customers: California law, disputes in San Francisco (Section 8).
- EU/UK customers: English law, disputes in London (GDPR, compliance_certifications.csv).
- Canadian customers: Ontario law, disputes in Toronto.

12.2 Contact
- **Legal**: legal@dataflow.com, +1-800-555-1234 (9 AM–5 PM PST).
- **Support**: support@dataflow.com (customer_support_procedures.md).
- **Mail**: DataFlow Solutions, 123 Market St, San Francisco, CA 94105, USA.
- **EU Representative**: DataFlow EU Ltd, 456 Oxford St, London, UK.

12.3 Definitions
- **User**: Individual or entity using the Platform.
- **Subscription**: Agreement for plan access (billing_and_pricing.csv).
- **Personal Data**: Per GDPR/CCPA (privacy_policy.txt).
- **SLA**: Service level agreement (customer_support_procedures.md).

12.4 Metrics
- Legal Queries: ~10/month (Zendesk).
- Response Time: 48 hours average (customer_support_procedures.md).
- Dispute Resolution: 90% informal (Section 8).

**Edge Case**: Multi-jurisdiction disputes (e.g., Customer 1009, customer_analytics.csv) prioritize GDPR for EU data (compliance_certifications.csv).
**Use Case**: Customer 1042 (customer_analytics.csv) contacts legal@dataflow.com for contract clarification, resolved in 24 hours (customer_support_procedures.md).

---

## References
- Billing and Pricing: billing_and_pricing.csv
- Privacy Policy: privacy_policy.txt
- Compliance Certifications: compliance_certifications.csv
- Customer Support Procedures: customer_support_procedures.md
- Security Policies: security_policies.txt
- API Documentation: api_documentation.json
- Product User Guide: product_user_guide.md
- Customer Analytics: customer_analytics.csv
- Sales Playbook: sales_playbook.json
- Incident Response Playbook: incident_response_playbook.txt
- Employee Handbook: employee_handbook.txt
- Integration Partners: integration_partners.csv
- Release Notes: release_notes.json
- System Architecture: system_architecture.md

## Revision History
- v2.5: June 8, 2025 – Added HIPAA clauses, updated arbitration for EU.
- v2.4: January 15, 2025 – Revised payment terms for international taxes.