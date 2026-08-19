from app.models import Society

def test_automation_cli_commands(app, runner):
    with app.app_context():
        society = Society.query.first()
        soc_id = society.id

    # 1. Test generate-monthly-bills
    res = runner.invoke(args=["generate-monthly-bills", "--society-id", str(soc_id)])
    assert res.exit_code == 0
    assert "Generated" in res.output

    # 2. Test apply-late-fees
    res = runner.invoke(args=["apply-late-fees", "--society-id", str(soc_id)])
    assert res.exit_code == 0
    assert "Applied late fees" in res.output

    # 3. Test send-maintenance-notifications
    res = runner.invoke(args=["send-maintenance-notifications", "--society-id", str(soc_id)])
    assert res.exit_code == 0
    assert "Sent" in res.output

    # 4. Test expire-visitor-passes
    res = runner.invoke(args=["expire-visitor-passes"])
    assert res.exit_code == 0
    assert "Expired" in res.output

    # 5. Test backup-database
    res = runner.invoke(args=["backup-database"])
    assert res.exit_code == 0
    assert "Database backup created" in res.output

    # 6. Test repair-receipts
    res = runner.invoke(args=["repair-receipts"])
    assert res.exit_code == 0
    assert "Audited and verified" in res.output
