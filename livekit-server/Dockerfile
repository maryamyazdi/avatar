FROM livekit/livekit-server:latest

# Expose LiveKit ports
# 7880: HTTP (WebRTC signaling)
# 7881: HTTPS (if using SSL)
# 7882: gRPC (for agent connections)
# 50000-60000: UDP (WebRTC media)
EXPOSE 7880 7881 7882
EXPOSE 50000-60000/udp

# Run LiveKit server in dev mode
CMD ["livekit-server", "--dev", "--bind", "0.0.0.0"]