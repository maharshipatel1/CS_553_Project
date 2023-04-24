import socket
import select
import errno
import sys

MAX_EVENTS = 100
BUFFER = 200
EXIT = 1
HOST = socket.gethostbyname(socket.gethostname())  # Get the IP address of the current machine
PORT = 8030
RESPONSE = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\nHello, world!\r\n"

# Creating a new server socket for this backend server
try: 
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
except socket.error as e: 
    print ("Error CREATING socket: {}".format(e)) 
    sys.exit(1)

# Binding the socket to a specific address and port
try: 
    server_socket.bind((HOST, PORT))
except socket.error as e: 
    print ("Error BINDING socket: {}".format(e)) 
    sys.exit(1)

# Non-blocking mode means it gives error when the call is suppose to block the program but because it generates an error we use that error to exit from the INFINITE loop
# Set the socket to nonblocking mode
server_socket.setblocking(0)


# Listening for incoming connections from the load balancer
try: 
    server_socket.listen(100)
except socket.error as e: 
    print ("Error LISTENING socket: {}".format(e)) 
    sys.exit(1)

print("Backend Server is listening at IP: {} Port: {}....".format(HOST,PORT))
print("\n")


# Creating an epoll instance
try:
    
    epoll = select.epoll()
    epoll.register(server_socket.fileno(), select.EPOLLIN | select.EPOLLET)
except OSError as e:
    print("Error in epoll instance: {}".format(e))
    sys.exit(1)


# The main execution of the server
try:
    connections = {}
    while True:
        
        # Setting the number of max connections
        try:
            events = epoll.poll(MAX_EVENTS)
        except OSError as e:
            print ("Error NO ready events: {}".format(e))
            sys.exit(1)

        for fileno, event in events:
        
            # Handle new connections
            if fileno == server_socket.fileno():
                #   onaccept(function) and choosing server and create connection to the selected server

                #   If no pending connections are present on the queue, and the
                #   socket is not marked as nonblocking, accept() blocks the caller
                #   until a connection is present.  If the socket is marked
                #   nonblocking and no pending connections are present on the queue,
                #   accept() fails with the error EAGAIN or EWOULDBLOCK.
                while True:
                    try:
                        client_connection, client_address = server_socket.accept()  
                    except socket.error as e:
                         if e.errno == (errno.EWOULDBLOCK | errno.EAGAIN):
                            break
                         else:
                            print("Can't establish connection with client: {}".format(e))
                            raise
                            
                    
                    client_connection.setblocking(0)
                    
                    # Setting the new connection as unblocking and adding it to the list of open connections
                    client_fd = client_connection.fileno()
                    epoll.register(client_fd, select.EPOLLIN | select.EPOLLET )
                    connections[client_fd] = client_connection
                    print("New Client connection from {} on socket: {}".format(client_address,client_fd))
            
            # Handle incoming data from the load balancer
            elif event & select.EPOLLIN:
                
                data = b""
                while True:
                
                    # Reading the incoming data from the load balancer
                    try:
                        chunk = connections[fileno].recv(BUFFER)
                        data += chunk
                    # exit from loop when all data is received => that is why the error statement
                    except socket.error as e:
                        if e.errno == (errno.EWOULDBLOCK | errno.EAGAIN):
                            break
                        else:
                            raise
                            
                # If we successfully recieve data, then we forward it to the backend server
                if data:
                    # on receive data code = receive data and 
                    print("Read Data: {}".format(data)) #Completed the basic step
                    print(len(data))
                    print("Sending Response....")
                    try:  
                        connections[fileno].send(RESPONSE)
                        # epoll.modify(fileno, select.EPOLLIN)
                    except socket.error as e:
                            raise
                    
                print("Closing Connection with client on socket {}".format(fileno))
                epoll.unregister(fileno)
                connections[fileno].close()
                del connections[fileno]
                print("\n")
                    
# Closing all of the allocated resources 
finally:
    epoll.unregister(server_socket.fileno())
    epoll.close()
    server_socket.close()
