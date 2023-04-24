import sys
import socket
import select
import errno
import random
from itertools import cycle

HOST = socket.gethostbyname(socket.gethostname())  # Get the IP address of the current machine
PORT = 8002
MAX_EVENTS = 100
BUFFER = 1024
SERVER_PORT = 8030
RESPONSE = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\nHello, world!\r\n"
SERVER_POOL = set(['128.6.4.103', '128.6.4.103'])

ITER = cycle(SERVER_POOL)

# Definiton of our Round-Robin Policy
def round_robin(iter):
    # round_robin([A, B, C, D]) --> A B C D A B C D A B C D ...
    return next(iter)



class LoadBalancer(object):
    """ Load balancer.
    
    Flow Diagram:-
    Client Socket <-> map(Client Socket, Server Socket) <-> Server Socket
    
    Notes:-
    flow_table is a dictionary that stores the mapping from the client socket to the server side socket
    sockets is a list that stores the currently connected and open server side sockets
    """

    flow_table = dict()
    ss_sockets = list()
    map_fd = {}
    
    # Initializng the attributes of our load balancer
    def __init__(self, algorithm='random'):
        self.algorithm = algorithm
        
        # Creating the load balancer's socket
        try: 
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        except socket.error as e: 
            print ("Error CREATING socket: {}".format(e)) 
            sys.exit(1)

        # Binding the socket to a specific address and port
        try: 
            self.server_socket.bind((HOST, PORT))
        except socket.error as e: 
            print ("Error BINDING socket: {}".format(e)) 
            sys.exit(1)

        # Non-blocking mode means it gives error when the call is suppose to block the program but because it generates an error we use that error to exit from the INFINITE loop
        # Set the socket to nonblocking mode
        self.server_socket.setblocking(0)
        
        # Listening for incoming connections
        try: 
            self.server_socket.listen(100)
        except socket.error as e: 
            print ("Error LISTENING socket: {}".format(e)) 
            sys.exit(1)

        print("Server is listening at IP: {} Port: {}....".format(HOST,PORT))
        print("\n")
        
        # Create an epoll instance
        try:
            self.epoll = select.epoll()
            self.epoll.register(self.server_socket.fileno(), select.EPOLLIN)
        except OSError as e:
            print("Error in epoll instance: {}".format(e))
            sys.exit(1)

    # A function that handles all new incoming connections
    # new conncention can be from any side = client or backened server
    def new_connection(self):
        try:
            # new conncention can be from any side = client or backened server
            client_socket, client_address = self.server_socket.accept()  
        except socket.error as e:
            print("Can't establish connection with client: {}".format(e))

        # selecting a backend server (IP address) based on the selected algorithm
        server_ip = self.select_server(SERVER_POOL, self.algorithm)
        
        # Creating a new server-side socket
        # Instantiating socket on load balancer in order to connect to the backend server
        ss_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        
        # Connecting the backend server
        try:
            ss_socket.connect((server_ip, SERVER_PORT))
            print("Load balancer: {} <=> Server connected: {}".format(ss_socket.getsockname(),(socket.gethostbyname(server_ip), SERVER_PORT)))
        except:
            print("Can't establish connection with the Backend Server {} ".format(server_ip))
            print("Closing Connection with client {} on socket {}".format(client_address,client_socket.fileno()))
            client_socket.close()
            return
        
        # Setting the client socket to non-blocking
        client_socket.setblocking(0)
        ss_socket.setblocking(0)

        self.ss_sockets.append(ss_socket.fileno())
        
         # Populating the flow table and the (client socket, server socket) mapping
        self.map_fd[client_socket.fileno()] = client_socket
        self.map_fd[ss_socket.fileno()] = ss_socket
        self.flow_table[client_socket.fileno()] = ss_socket.fileno()
        self.flow_table[ss_socket.fileno()] = client_socket.fileno()

        # Epoll instance monitoring server-side socket to recieve data
        self.epoll.register(ss_socket.fileno(), select.EPOLLIN)
        
        # Epoll instanec monitoring client-side socket to recieve data
        self.epoll.register(client_socket.fileno(), select.EPOLLIN) 

        
        print("New CLIENT connection from {} on socket: {}".format(client_address,client_socket.fileno()))
        print("New connection with BACKEND SERVER {} on socket: {}".format((server_ip, SERVER_PORT),ss_socket.fileno()))


        # self.sockets.append(client_socket)
        # self.sockets.append(ss_socket)

        
    # A function that handles incoming data on a socket
    def on_recv(self,fd, msg):
        
        # incoming message = request from CLIENT -> we need to forward it to the selected server 
        # Stateful scenario -> Identify cookie from data here and take action accordingly
        # ss_fd = self.flow_table[fd]
        
        ss_socket = self.map_fd[self.flow_table[fd]]
        try:
            print("Forwarding packets from socket: {} to socket: {}".format(fd,ss_socket.fileno()))
            ss_socket.send(msg)
            
        except socket.error as e:
            if e.errno == errno.EWOULDBLOCK:
                pass
            else:
                raise
        
        
        if fd in self.ss_sockets:
            print("Closing Connection with client and backend server on socket {} and {}".format(self.flow_table[fd],fd))
            self.map_fd[fd].close()
            self.map_fd[self.flow_table[fd]].close()

            del self.flow_table[self.flow_table[fd]]
            del self.flow_table[fd]
      

           
    # A function that selects a backend server based on the selected policy     
    def select_server(self, server_list, algorithm):
            if algorithm == 'random':
                return random.choice(server_list)
            elif algorithm == 'round robin':
                return round_robin(ITER)
            else:
                raise Exception('unknown algorithm: {}'.format(algorithm) )



    # The main exectution of the load balancer
    def start(self):
        try:
            while True:
                try:
                    events = self.epoll.poll(MAX_EVENTS)
                except OSError as e:
                    print ("Error NO ready events: {}".format(e)) 
                    sys.exit(1)

                for fileno, event in events:
                
                    # Handling new connections
                    if fileno == self.server_socket.fileno():
                        # onaccept(function) and choosing server and create connection to the selected server
                        self.new_connection()
                    
                     # Handling incoming data    
                    else:
                        
                        data = b""
                        
                        while True:
                            try:
                                chunk = self.map_fd[fileno].recv(BUFFER)
                                # exit from loop when all data is received
                                if not chunk:
                                    break
                                data += chunk

                            except socket.error as e:
                                if e.errno == errno.EWOULDBLOCK:
                                    break
                                else:
                                    raise
                        
                        # If new data is successfully received
                        if data:
                            
                            print("Read Data: {}".format(data))
                            self.on_recv(fileno,data)
      

        # Closing all the allocated resources
        finally:
            self.epoll.unregister(self.server_socket.fileno())
            self.epoll.close()
            self.server_socket.close()

    

if __name__ == '__main__':
    
    try:
        LoadBalancer('round robin').start()
    except KeyboardInterrupt:
        print ("Ctrl C - Stopping load_balancer")
        sys.exit(1)
