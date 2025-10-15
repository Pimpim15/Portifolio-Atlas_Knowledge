locals {
  cost_budget_name = "atlas-${var.environment}-monthly"
}

resource "aws_budgets_budget" "monthly" {
  count                     = var.enable_cost_budget && length(var.cost_budget_emails) > 0 ? 1 : 0
  name                      = local.cost_budget_name
  budget_type               = "COST"
  time_unit                 = "MONTHLY"
  budget_limit {
    amount = var.cost_budget_amount
    unit   = "USD"
  }

  cost_types {
    include_credit             = false
    include_refund             = false
    include_tax                = true
    include_subscription       = true
    include_upfront            = true
    include_support            = true
    include_recurring          = true
    include_other_subscription = true
    include_discount           = true
    use_amortized              = true
    use_blended                = false
  }

  notification {
    comparison_operator          = "GREATER_THAN"
    threshold                    = var.cost_budget_threshold_percent
    threshold_type               = "PERCENTAGE"
    notification_type            = "ACTUAL"
    dynamic "subscriber" {
      for_each = var.cost_budget_emails
      content {
        subscription_type = "EMAIL"
        address           = subscriber.value
      }
    }
  }

  notification {
    comparison_operator          = "GREATER_THAN"
    threshold                    = var.cost_budget_threshold_percent
    threshold_type               = "PERCENTAGE"
    notification_type            = "FORECASTED"
    dynamic "subscriber" {
      for_each = var.cost_budget_emails
      content {
        subscription_type = "EMAIL"
        address           = subscriber.value
      }
    }
  }
}
