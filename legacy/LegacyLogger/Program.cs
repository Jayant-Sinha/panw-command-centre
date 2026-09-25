var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var now = DateTimeOffset.UtcNow;

var logs = new[]
{
    new RawLogEntry(now, "192.168.1.1", "Login Attempt", "Success"),
    new RawLogEntry(now.AddSeconds(-5), "45.33.22.11", "SSH Connection", "Failed"),
    new RawLogEntry(now.AddSeconds(-10), "10.0.0.5", "File Access", "Denied")
};

app.MapGet("/api/raw-logs", () => TypedResults.Ok(logs));

app.Run("http://localhost:5042");

internal sealed record RawLogEntry(
    DateTimeOffset Timestamp,
    string Source,
    string Event,
    string Status);
