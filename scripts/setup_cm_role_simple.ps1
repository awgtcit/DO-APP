$server = "172.50.35.75"
$database = "mtcintranet1"
$username = "sa"
$password = "Admin@123"

Write-Host "Setting up Customer Manager role for delivery orders..." -ForegroundColor Green

$connectionString = "Server=$server;Database=$database;User Id=$username;Password=$password;Connection Timeout=30;TrustServerCertificate=Yes;"

$connection = New-Object System.Data.SqlClient.SqlConnection
$connection.ConnectionString = $connectionString

try {
    $connection.Open()
    Write-Host "✓ Connected to $server\$database" -ForegroundColor Green

    # Get the delivery_orders module ID
    $query = "SELECT id FROM Intra_Admin_ModuleConfig WHERE module_key = 'delivery_orders'"
    $command = New-Object System.Data.SqlClient.SqlCommand($query, $connection)
    $moduleId = $command.ExecuteScalar()

    if ($moduleId) {
        Write-Host "✓ Found delivery_orders module (ID: $moduleId)" -ForegroundColor Green

        # Find an employee who created orders
        $empQuery = "SELECT TOP 1 Created_by FROM Intra_SalesOrder WHERE Created_by IS NOT NULL ORDER BY ID DESC"
        $command = New-Object System.Data.SqlClient.SqlCommand($empQuery, $connection)
        $empId = $command.ExecuteScalar()

        if ($empId) {
            Write-Host "✓ Found employee $empId" -ForegroundColor Green

            # Assign the customer manager role
            $insertQuery = @"
            MERGE Intra_Admin_UserModuleRole AS t
            USING (SELECT $moduleId AS module_id, $empId AS emp_id, 'do_customer_manager' AS role_key) AS s
            ON t.module_id = s.module_id AND t.emp_id = s.emp_id AND t.role_key = s.role_key
            WHEN NOT MATCHED THEN
                INSERT (module_id, emp_id, role_key, assigned_by, assigned_at)
                VALUES (s.module_id, s.emp_id, s.role_key, 1, GETDATE());
"@

            $command = New-Object System.Data.SqlClient.SqlCommand($insertQuery, $connection)
            $rowsAffected = $command.ExecuteNonQuery()
            Write-Host "✓ Assigned do_customer_manager role to employee $empId!" -ForegroundColor Green
        }
        else {
            Write-Host "✗ No employees found" -ForegroundColor Red
        }
    }
    else {
        Write-Host "✗ Delivery Orders module not found!" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "Setup complete! The user with emp_id=$empId now has the Customer Manager role." -ForegroundColor Green
    Write-Host "They should see the 'Approve' button when viewing orders in PENDING CUSTOMER APPROVAL status." -ForegroundColor Green

}
catch {
    Write-Host "✗ ERROR: $_" -ForegroundColor Red
}
finally {
    $connection.Close()
    $connection.Dispose()
}
