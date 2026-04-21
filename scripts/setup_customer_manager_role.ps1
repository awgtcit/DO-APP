# Script to assign customer manager role to a test user
# This enables testing the approval workflow

# Database connection details (from environment or use defaults)
$server = $env:DB_SERVER -or "172.50.35.75"
$database = $env:DB_NAME -or "mtcintranet1"
$username = $env:DB_USER -or "sa"
$password = $env:DB_PASSWORD

$connectionString = "Server=$server;Database=$database;User Id=$username;Password=$password;Connection Timeout=30;TrustServerCertificate=Yes;"

Write-Host "Connecting to SQL Server: $server\$database..." -ForegroundColor Green

$connection = New-Object System.Data.SqlClient.SqlConnection
$connection.ConnectionString = $connectionString

try {
    $connection.Open()
    Write-Host "Connected successfully!" -ForegroundColor Green

    # Get the delivery_orders module ID
    $query = @"
    SELECT TOP 1 id FROM Intra_Admin_ModuleConfig WHERE module_key = 'delivery_orders'
"@

    $command = New-Object System.Data.SqlClient.SqlCommand
    $command.Connection = $connection
    $command.CommandText = $query

    $moduleId = $command.ExecuteScalar()

    if ($moduleId) {
        Write-Host "Found Delivery Orders module (ID: $moduleId)" -ForegroundColor Green

        # Find an employee who created orders
        $empQuery = @"
        SELECT TOP 1
            Created_by as emp_id
        FROM Intra_SalesOrder
        WHERE Created_by IS NOT NULL
        ORDER BY ID DESC
"@

        $command.CommandText = $empQuery
        $empId = $command.ExecuteScalar()

        if ($empId) {
            Write-Host "Found employee ID: $empId (created orders)" -ForegroundColor Green

            # Check if already assigned
            $checkQuery = @"
            SELECT COUNT(*) FROM Intra_Admin_UserModuleRole
            WHERE module_id = @moduleId AND emp_id = @empId AND role_key = 'do_customer_manager'
"@

            $command.CommandText = $checkQuery
            $command.Parameters.Clear()
            $command.Parameters.AddWithValue("@moduleId", $moduleId)
            $command.Parameters.AddWithValue("@empId", $empId)

            $alreadyAssigned = $command.ExecuteScalar()

            if ($alreadyAssigned -gt 0) {
                Write-Host "Role already assigned to employee $empId" -ForegroundColor Yellow
            } else {
                # Assign the role
                $assignQuery = @"
                INSERT INTO Intra_Admin_UserModuleRole (module_id, emp_id, role_key, assigned_by, assigned_at)
                VALUES (@moduleId, @empId, 'do_customer_manager', 1, GETDATE())
"@

                $command.CommandText = $assignQuery
                $command.Parameters.Clear()
                $command.Parameters.AddWithValue("@moduleId", $moduleId)
                $command.Parameters.AddWithValue("@empId", $empId)

                $rowsAffected = $command.ExecuteNonQuery()
                Write-Host "Assigned do_customer_manager role to employee $empId!" -ForegroundColor Green
            }
        } else {
            Write-Host "No employees found who created orders. Using default employee ID 1001." -ForegroundColor Yellow

            $empId = 1001

            # Assign the role
            $assignQuery = @"
            MERGE Intra_Admin_UserModuleRole AS t
            USING (SELECT @moduleId AS module_id, @empId AS emp_id, 'do_customer_manager' AS role_key) AS s
            ON t.module_id = s.module_id AND t.emp_id = s.emp_id AND t.role_key = s.role_key
            WHEN NOT MATCHED THEN
                INSERT (module_id, emp_id, role_key, assigned_by, assigned_at)
                VALUES (@moduleId, @empId, 'do_customer_manager', 1, GETDATE());
"@

            $command.CommandText = $assignQuery
            $command.Parameters.Clear()
            $command.Parameters.AddWithValue("@moduleId", $moduleId)
            $command.Parameters.AddWithValue("@empId", $empId)

            $rowsAffected = $command.ExecuteNonQuery()
            Write-Host "Assigned do_customer_manager role to employee $empId" -ForegroundColor Green
        }
    } else {
        Write-Host "ERROR: Delivery Orders module not found!" -ForegroundColor Red

        $allModules = @"
        SELECT id, module_key FROM Intra_Admin_ModuleConfig
"@
        $command.CommandText = $allModules
        $command.Parameters.Clear()
        $reader = $command.ExecuteReader()
        Write-Host "Available modules:" -ForegroundColor Yellow
        while ($reader.Read()) {
            Write-Host "  ID: $($reader['id']), Key: $($reader['module_key'])" -ForegroundColor Yellow
        }
        $reader.Close()
    }

} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
} finally {
    $connection.Close()
    $connection.Dispose()
}

Write-Host "Setup complete!" -ForegroundColor Green
